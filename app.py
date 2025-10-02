import streamlit as st
from init import initialize_app
from ui_components import render_header, render_footer
import config as cf
import ui_components
import helpers as hp

st.set_page_config(
    page_title=cf.APP_TITLE,
    page_icon=":guardsman:",
    layout="wide"
)

if not st.session_state.get("initialized"):
    try:
        initialize_app()
        st.session_state.initialized = True
        logger = st.session_state.get("logger")
        if logger:
            logger.info(cf.APP_START_MESSAGE)
        else:
            print(cf.APP_START_MESSAGE)
    except Exception as e:
        logger = st.session_state.get("logger")
        msg = f"{cf.ERROR_MSG_INIT_FAILED}\n{e}"
        if logger:
            logger.error(msg)
        else:
            print(msg)
        st.error(ui_components.compose_error_message(cf.ERROR_MSG_INIT_FAILED))
        st.stop()
else:
    logger = st.session_state.get("logger")

for k, v in {
    "flow_step": 0, "flow_mode": None,
    "flow_is_generating": False, "flow_pending_q": "",
    "is_generating": False, "user_id": st.session_state.get("user_id", ""),
    "_scroll_bottom": False,
}.items():
    st.session_state.setdefault(k, v)

with st.sidebar:
    st.markdown("### ユーザー設定")
    uid = st.text_input("ユーザーID（履歴の保存/読込に使用）",
                        value=st.session_state.get("user_id", ""), key="user_id_input")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("履歴ロード", use_container_width=True, key="btn_load_history"):
            st.session_state.user_id = uid.strip()
            loaded = hp.load_history(st.session_state.user_id)
            st.success("履歴を読み込みました。" if loaded else "履歴がなかったので新規作成しました。")
            st.rerun()
    with col_b:
        if st.button("履歴保存", use_container_width=True, key="btn_save_history"):
            st.session_state.user_id = uid.strip()
            # autosave を確実に発火させる
            hp.append_message("__noop__", "")
            st.session_state.messages = [
                m for m in st.session_state.messages if m["role"] != "__noop__"]
            st.success("履歴を保存しました。")
    with col_c:
        if st.button("履歴クリア", use_container_width=True, key="btn_clear_history"):
            st.session_state.messages = []
            st.success("履歴をクリアしました。")

render_header()
hp.show_initial_ai_message()

st.markdown("### ステップ式フロー")

if st.session_state.flow_step == 0:
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("学部・学科について", use_container_width=True, key="btn_step1"):
            st.session_state.flow_step = 1
            st.session_state.flow_mode = None
            st.rerun()
    with col2:
        if st.button("研究室を調べたい", use_container_width=True, key="btn_step2"):
            st.session_state.flow_step = 3
            st.session_state.flow_mode = "research"
            st.rerun()
    with col3:
        if st.button("大学生活を知りたい", use_container_width=True, key="btn_step3"):
            st.session_state.flow_step = 4
            st.session_state.flow_mode = "campus"
            st.rerun()

elif st.session_state.flow_step == 1:
    st.info("【学部・学科】どちらを調べますか？")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("学部", use_container_width=True, key="btn_faculty"):
            st.session_state.flow_mode = "faculty"
            st.session_state.flow_step = 2
            st.rerun()
    with col2:
        if st.button("学科", use_container_width=True, key="btn_department"):
            st.session_state.flow_mode = "department"
            st.session_state.flow_step = 2
            st.rerun()
    with col3:
        if st.button("← 入口へ戻る", use_container_width=True, key="btn_back_home_from1"):
            st.session_state.flow_step = 0
            st.session_state.flow_mode = None
            st.rerun()

elif st.session_state.flow_step == 2:
    mode_label = "学部" if st.session_state.flow_mode == "faculty" else "学科"
    st.info(
        f"【{mode_label}】のみを参照して回答します。"
    )

    for m in st.session_state.get("messages", []):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if st.session_state.get("flow_is_generating"):
        with st.spinner("回答を生成中..."):
            try:
                pending_q = st.session_state.get("flow_pending_q", "").strip()
                if pending_q:
                    if logger:
                        logger.debug(
                            f"[RAG] mode={st.session_state.flow_mode} pending_q={pending_q}")
                    llm_response = ui_components.get_llm_response(
                        pending_q, mode=st.session_state.flow_mode
                    )
                    ai_content = llm_response.get("answer", "AI回答生成に失敗しました。")
                    hp.append_message("assistant", ai_content)
            except Exception as e:
                msg = f"{cf.ERROR_MSG_LLM_RESPONSE_FAILED}\n{e}"
                (logger.error(msg) if logger else print(msg))
                st.error(cf.ERROR_MSG_LLM_RESPONSE_FAILED)
            finally:
                st.session_state.flow_is_generating = False
                st.session_state.flow_pending_q = ""
                st.session_state._scroll_bottom = True
                st.rerun()

    with st.form("flow_query_form_12", clear_on_submit=True):
        q = st.text_input(f"{mode_label}について知りたいことを入力",
                          key="flow_query_input_12")
        submitted = st.form_submit_button("送信")

    cols = st.columns([1, 1])
    with cols[1]:
        if st.button("← 選び直す", use_container_width=True, key="btn_back_step1"):
            st.session_state.flow_step = 1
            st.session_state.flow_mode = None
            st.rerun()

    if submitted and q.strip():
        hp.append_message("user", f"[{mode_label}] {q.strip()}")
        st.session_state.user_id = st.session_state.get(
            "user_id_input", "").strip()
        st.session_state.flow_pending_q = q.strip()
        st.session_state.flow_is_generating = True
        st.rerun()

    if st.session_state.get("_scroll_bottom"):
        st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)
        st.markdown("""
            <script>
              const el = document.getElementById("chat-bottom");
              if (el) { el.scrollIntoView({behavior: "instant", block: "end"}); }
            </script>
        """, unsafe_allow_html=True)
        st.session_state._scroll_bottom = False

# ===== 研究室 入力（Step2） flow_step=3 =====
elif st.session_state.flow_step == 3:
    st.info("【研究室】のみを参照して回答します。")

    # 履歴描画
    for m in st.session_state.get("messages", []):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 生成中（mode='research' を確実に渡す）
    if st.session_state.get("flow_is_generating"):
        with st.spinner("回答を生成中..."):
            try:
                pending_q = st.session_state.get("flow_pending_q", "").strip()
                if pending_q:
                    if logger:
                        logger.debug(
                            f"[RAG] mode=research pending_q={pending_q}")
                    llm_response = ui_components.get_llm_response(
                        pending_q, mode="research")
                    ai_content = llm_response.get("answer", "AI回答生成に失敗しました。")
                    hp.append_message("assistant", ai_content)
            except Exception as e:
                msg = f"{cf.ERROR_MSG_LLM_RESPONSE_FAILED}\n{e}"
                (logger.error(msg) if logger else print(msg))
                st.error(cf.ERROR_MSG_LLM_RESPONSE_FAILED)
            finally:
                st.session_state.flow_is_generating = False
                st.session_state.flow_pending_q = ""
                st.session_state._scroll_bottom = True
                st.rerun()

    with st.form("flow_query_form_3", clear_on_submit=True):
        q = st.text_input("研究室について知りたいことを入力", key="flow_query_input_3")
        submitted = st.form_submit_button("送信")

    cols = st.columns([1, 1])
    with cols[1]:
        if st.button("← 入口へ戻る", use_container_width=True, key="btn_back_home_from3"):
            st.session_state.flow_step = 0
            st.session_state.flow_mode = None
            st.rerun()

    if submitted and q.strip():
        hp.append_message("user", f"[研究室] {q.strip()}")
        st.session_state.user_id = st.session_state.get(
            "user_id_input", "").strip()
        st.session_state.flow_pending_q = q.strip()
        st.session_state.flow_is_generating = True
        st.rerun()

    if st.session_state.get("_scroll_bottom"):
        st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)
        st.markdown("""
            <script>
              const el = document.getElementById("chat-bottom");
              if (el) { el.scrollIntoView({behavior: "instant", block: "end"}); }
            </script>
        """, unsafe_allow_html=True)
        st.session_state._scroll_bottom = False

elif st.session_state.flow_step == 4:
    st.info("【大学生活】のみを参照して回答します。")

    for m in st.session_state.get("messages", []):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if st.session_state.get("flow_is_generating"):
        with st.spinner("回答を生成中..."):
            try:
                pending_q = st.session_state.get("flow_pending_q", "").strip()
                if pending_q:
                    if logger:
                        logger.debug(
                            f"[RAG] mode=campus pending_q={pending_q}")
                    llm_response = ui_components.get_llm_response(
                        pending_q, mode="campus")
                    ai_content = llm_response.get("answer", "AI回答生成に失敗しました。")
                    hp.append_message("assistant", ai_content)
            except Exception as e:
                msg = f"{cf.ERROR_MSG_LLM_RESPONSE_FAILED}\n{e}"
                (logger.error(msg) if logger else print(msg))
                st.error(cf.ERROR_MSG_LLM_RESPONSE_FAILED)
            finally:
                st.session_state.flow_is_generating = False
                st.session_state.flow_pending_q = ""
                st.session_state._scroll_bottom = True
                st.rerun()

    # 入力フォーム
    with st.form("flow_query_form_4", clear_on_submit=True):
        q = st.text_input("大学生活について知りたいことを入力", key="flow_query_input_4")
        submitted = st.form_submit_button("送信")

    cols = st.columns([1, 1])
    with cols[1]:
        if st.button("← 入口へ戻る", use_container_width=True, key="btn_back_home_from4"):
            st.session_state.flow_step = 0
            st.session_state.flow_mode = None
            st.rerun()

    if submitted and q.strip():
        hp.append_message("user", f"[大学生活] {q.strip()}")
        st.session_state.user_id = st.session_state.get(
            "user_id_input", "").strip()
        st.session_state.flow_pending_q = q.strip()
        st.session_state.flow_is_generating = True
        st.rerun()

    if st.session_state.get("_scroll_bottom"):
        st.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)
        st.markdown("""
            <script>
              const el = document.getElementById("chat-bottom");
              if (el) { el.scrollIntoView({behavior: "instant", block: "end"}); }
            </script>
        """, unsafe_allow_html=True)
        st.session_state._scroll_bottom = False


if st.session_state.flow_step == 0:
    if not st.session_state.get("is_generating", False):
        try:
            hp.render_conversation_log()
        except Exception as e:
            msg = f"{cf.ERROR_MSG_DISPLAY_ANSWER_FAILED}\n{e}"
            (logger.error(msg) if logger else print(msg))
            st.error(ui_components.compose_error_message(
                cf.ERROR_MSG_DISPLAY_ANSWER_FAILED))
            st.stop()

    if st.session_state.get("is_generating"):
        last_user = st.session_state.messages[-1]["content"] if st.session_state.messages else ""
        if last_user:
            with st.chat_message("user"):
                st.markdown(last_user)
        with st.spinner("回答を生成中..."):
            try:
                llm_response = ui_components.get_llm_response(
                    last_user, mode=None)
                ai_content = llm_response.get("answer", "AI回答生成に失敗しました。")
                hp.append_message("assistant", ai_content)
                st.session_state.is_generating = False
                st.rerun()
            except Exception as e:
                msg = f"{cf.ERROR_MSG_LLM_RESPONSE_FAILED}\n{e}"
                (logger.error(msg) if logger else print(msg))
                st.session_state.is_generating = False
                st.error(cf.ERROR_MSG_LLM_RESPONSE_FAILED)
                st.stop()

    chat_input = st.chat_input(cf.CHAT_INPUT_PLACEHOLDER)
    if chat_input and not st.session_state.is_generating:
        st.session_state.is_generating = True
        hp.append_message("user", chat_input)
        st.rerun()

# フッター
render_footer()
