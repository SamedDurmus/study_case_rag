"""Streamlit ana uygulama.

Belge yükleme, işleme ve soru-cevap arayüzü.
"""

import logging
import tempfile
from pathlib import Path

import streamlit as st

from src.config import OLLAMA_MODEL, QDRANT_URL
from src.document_processing.smart_loader import SmartLoader, SUPPORTED_EXTENSIONS
from src.generation.chain import RAGChain, NO_CONTEXT_RESPONSE, INJECTION_RESPONSE
from src.generation.llm import LLMClient
from src.indexing.chunker import chunk_documents
from src.indexing.embedder import Embedder
from src.security.document_guard import check_document_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Sayfa Ayarları ---
st.set_page_config(
    page_title="Belge Analiz & Soru-Cevap",
    page_icon="📄",
    layout="wide",
)

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "documents" not in st.session_state:
    st.session_state.documents = []
if "embedder" not in st.session_state:
    st.session_state.embedder = Embedder()
if "chain" not in st.session_state:
    chain = RAGChain()
    # BGE-M3 modelini embedder ile paylaş (iki kez yüklemeyi önle)
    chain._searcher.set_model(st.session_state.embedder._get_model())
    st.session_state.chain = chain
if "loader" not in st.session_state:
    st.session_state.loader = SmartLoader()


# --- Sidebar ---
with st.sidebar:
    st.header("Belge Yükleme")

    uploaded_files = st.file_uploader(
        "PDF veya resim dosyaları yükleyin",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

    if st.button("Belgeleri İşle", type="primary", disabled=not uploaded_files):
        with st.spinner("Belgeler işleniyor..."):
            embedder: Embedder = st.session_state.embedder
            loader: SmartLoader = st.session_state.loader

            # Önceki collection'ı temizle
            try:
                embedder.delete_collection()
            except Exception:
                pass

            all_chunks = []
            doc_info = []

            for uploaded_file in uploaded_files:
                # Geçici dosyaya yaz
                suffix = Path(uploaded_file.name).suffix
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix
                ) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name

                try:
                    result = loader.load(tmp_path, original_filename=uploaded_file.name)

                    # Document guard — indirect injection kontrolü
                    for chunk in result.chunks:
                        threats = check_document_content(chunk.text, uploaded_file.name)
                        if threats:
                            st.warning(
                                f"'{uploaded_file.name}' belgesinde şüpheli içerik tespit edildi: "
                                f"{', '.join(threats)}. İçerik temizlenerek işlendi."
                            )
                            break

                    chunked = chunk_documents(result.chunks)
                    all_chunks.extend(chunked)

                    doc_info.append({
                        "name": uploaded_file.name,
                        "pages": result.total_pages,
                        "method": result.extraction_method,
                        "chunks": len(chunked),
                    })
                except Exception as e:
                    st.error(f"Hata ({uploaded_file.name}): {e}")
                    logger.error("Dosya isleme hatasi: %s - %s", uploaded_file.name, e)

            # Qdrant'a yaz
            if all_chunks:
                try:
                    indexed = embedder.embed_and_index(all_chunks)
                    st.session_state.documents = doc_info
                    st.success(
                        f"{len(doc_info)} belge işlendi, "
                        f"{indexed} chunk indekslendi."
                    )
                except Exception as e:
                    st.error(f"İndeksleme hatası: {e}")
                    logger.error("Indeksleme hatasi: %s", e)

    # Yüklü belgeler listesi
    if st.session_state.documents:
        st.divider()
        st.subheader("Yüklü Belgeler")
        for doc in st.session_state.documents:
            st.markdown(
                f"**{doc['name']}**  \n"
                f"Sayfa: {doc['pages']} | "
                f"Yöntem: {doc['method']} | "
                f"Chunk: {doc['chunks']}"
            )

    # Sistem durumu
    st.divider()
    st.subheader("Sistem Durumu")
    st.markdown(f"**Model:** {OLLAMA_MODEL}")

    llm_client = LLMClient()
    if llm_client.check_connection():
        st.markdown("**Ollama:** Bağlı ✓")
    else:
        st.markdown("**Ollama:** Bağlantı yok ✗")

    try:
        from qdrant_client import QdrantClient
        qclient = QdrantClient(url=QDRANT_URL)
        qclient.get_collections()
        st.markdown("**Qdrant:** Bağlı ✓")
    except Exception:
        st.markdown("**Qdrant:** Bağlantı yok ✗")


# --- Ana Alan ---
st.title("Belge Analiz & Soru-Cevap Sistemi")

if not st.session_state.documents:
    st.info("Başlamak için sol panelden belge yükleyin ve 'Belgeleri İşle' butonuna tıklayın.")

# Chat geçmişini göster
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Kullanıcı girişi
if question := st.chat_input("Belgeler hakkında bir soru sorun..."):
    # Kullanıcı mesajını ekle
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Belge yüklü mü kontrol
    if not st.session_state.documents:
        response = "Lütfen önce bir belge yükleyin."
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
    else:
        # RAG pipeline ile cevap üret (streaming)
        with st.chat_message("assistant"):
            chain: RAGChain = st.session_state.chain

            try:
                stream, sources, has_context, warnings = chain.query_stream(question)

                # Input guard tarafından engellendi
                if warnings and not has_context and stream is None:
                    blocked_msg = warnings[0] if warnings else INJECTION_RESPONSE
                    st.warning(blocked_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": blocked_msg,
                    })
                elif not has_context:
                    st.markdown(NO_CONTEXT_RESPONSE)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": NO_CONTEXT_RESPONSE,
                    })
                else:
                    response = st.write_stream(stream)

                    # Uyarılar varsa göster
                    for w in warnings:
                        st.caption(f"⚠ {w}")

                    # Kaynak bilgileri
                    if sources:
                        source_text = "\n".join(
                            f"- {s['source_file']}, Sayfa {s['page_number']}"
                            for s in sources
                        )
                        st.caption(f"**Kaynaklar:**\n{source_text}")

                    full_response = response if isinstance(response, str) else str(response)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": full_response,
                    })
            except Exception as e:
                error_msg = f"Cevap üretilirken hata oluştu: {e}"
                st.error(error_msg)
                logger.error("RAG chain hatasi: %s", e)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                })
