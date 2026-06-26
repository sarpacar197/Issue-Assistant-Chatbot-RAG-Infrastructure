import streamlit as st
import requests, uuid, os, html
from langchain_core.messages import HumanMessage
from orchestrate import orchestrator
from agent_core import fetch_data_from_image

st.set_page_config("Issue Temp", layout="wide")
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

#---------------------------------------------------------------#

st.markdown("""
<style>
@font-face { font-family:'Gilroy'; src: local('Gilroy'), local('Gilroy-Bold'); font-weight:bold; }
.app-title{ font-family:'Gilroy','Segoe UI',sans-serif; font-weight:800;
            font-size:36px; color:#1A1A1A; margin:4px 0 16px 0; }
.msg-user{ background:#0B5FFF; color:#fff; padding:10px 14px; border-radius:12px;
           margin:6px 0 6px auto; max-width:72%; width:fit-content; }
.msg-bot{ background:#F2F4F7; color:#1A1A1A; padding:10px 14px; border-radius:12px;
          margin:6px auto 6px 0; max-width:72%; width:fit-content; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-title">Issue Asistanı</div>', unsafe_allow_html=True)

#---------------------------------------------------------------#
def new_chat():
    cid = str(uuid.uuid4())
    st.session_state.chats[cid] = {"title": "Yeni sohbet", "history": [],
                                   "thread_id": str(uuid.uuid4())}
    st.session_state.current = cid
    st.session_state.show_form = False
    st.session_state.form_data = {}

if "chats" not in st.session_state:
    st.session_state.chats = {}
    st.session_state.current = None
    st.session_state.show_form = False
    st.session_state.form_data = {}
    new_chat()
#---------------------------------------------------------------#

with st.sidebar:
    st.header("New Chats")
    if st.button(" Yeni sohbet", use_container_width=True):
        new_chat(); st.rerun()
    st.divider()
    for cid, c in reversed(list(st.session_state.chats.items())):
        if st.button(c["title"], key = cid, use_container_width=True):
            st.session_state.current = cid
            st.session_state.show_form = False
            st.rerun()

chat = st.session_state.chats[st.session_state.current]
#---------------------------------------------------------------#
for role,text in chat["history"]:
    cls = "msg-user" if role == "user" else "msg-bot"
    safe = html.escape(text).replace("\n", "<br>")
    st.markdown(f'<div class="{cls}">{safe}</div>', unsafe_allow_html=True)

#---------------------------------------------------------------#
if prompt := st.chat_input("Mesaj yaz ..."):
    chat["history"].append(("user", prompt))
    if chat["title"] == "Yeni sohbet":
        chat["title"] = (prompt[:30] + "…") if len(prompt) > 30 else prompt
    config = {"configurable" : {"thread_id": chat["thread_id"]}}
    with st.spinner("Devam..."):
        r = orchestrator.invoke({"messages": [HumanMessage(prompt)]}, config=config)
    if r.get("route") == "issue":
        st.session_state.show_form = True
        chat["history"].append(("assistant", "Issue açmak için formu doldur (foto da yükleyebilirsin)."))
    else:
        chat["history"].append(("assistant", r["messages"][-1].content))
    st.rerun() 

#------------------------ FORM------------------------------------#

if st.session_state.show_form:
    fotos = st.file_uploader("Complaint formu fotoğrafları (opsiyonel)",
                             type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if fotos and st.button("Fotodan doldur"):
        with st.spinner("Analyzing images"):
            data = fetch_data_from_image([f.read() for f in fotos])
        if data:
            st.session_state.form_data = data
            st.success("Bilgiler çıkarıldı, formu kontrol et.")
        else:
            st.warning("Hata")

    fd = st.session_state.form_data
    with st.form("issue_form"):
        st.subheader("New Issue")
        title = st.text_input("title *", value=fd.get("title", ""))
        description = st.text_area("description *", value=fd.get("description", ""))
        pri_list = ["low", "medium", "high"]
        pri_def = fd.get("priority", "low")
        priority = st.selectbox("Öncelik *", pri_list,
                                index=pri_list.index(pri_def) if pri_def in pri_list else 0)
        assignee_name = st.text_input("Atanan Kişi *", value=fd.get("assignee_name", ""))
        assignee_email = st.text_input("E-posta *", value=fd.get("assignee_email", ""))
        submit = st.form_submit_button("Issue Create")

    if submit:
        if not all([title, description, assignee_name, assignee_email]):
            st.error("Hata")
        else:
            try:
                resp = requests.post(f"{API_URL}/issues", json={
                    "title": title, "description": description, "priority": priority,
                    "assignee_name": assignee_name, "assignee_email": assignee_email,
                })

                if resp.status_code == 200:
                    chat["history"].append(("assistant", f"Issue açıldı: #{resp.json()['id']} '{title}'"))
                    st.session_state.show_form = False
                    st.session_state.form_data = {}
                    st.rerun()
                else:
                    st.error(f"Hata: {resp.text}")



            except Exception as e:
                    st.error(f"Connection Error: {e}")


