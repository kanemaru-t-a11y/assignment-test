"""
helpers.py
画面表示以外の汎用関数を定義
"""
import os
import json
import streamlit as st
import config as cf


def show_initial_ai_message():  # 初期メッセージ表示
    st.info("Campus Guide AIへようこそ。学内の情報検索をお手伝いします。質問があればお気軽にどうぞ。")  # 初期メッセージ表示


def _trim_history_inplace():  # 履歴のトリム
    """保存上限を超えたら古い順に削除"""
    msgs = st.session_state.get("messages", [])  # メッセージ履歴取得
    maxn = getattr(cf, "MAX_HISTORY_MESSAGES", 50)  # 上限取得
    if len(msgs) > maxn:  # 上限超過
        st.session_state.messages = msgs[-maxn:]  # トリム


def append_message(role: str, content: str):  # メッセージ追加
    """履歴に追記し、必要なら自動保存"""
    st.session_state.setdefault("messages", [])  # メッセージ履歴初期化
    st.session_state.messages.append({"role": role, "content": content})  # 追加
    _trim_history_inplace()  # トリム
    if getattr(cf, "AUTOSAVE_HISTORY", True):  # 自動保存設定
        _autosave_history()  # 自動保存


def render_conversation_log():  # 会話ログ表示
    """会話ログの表示（全件。トリムは保存時にかけている）"""
    msgs = st.session_state.get("messages", [])  # メッセージ履歴取得
    for message in msgs:  # 全メッセージ表示
        with st.chat_message(message["role"]):  # 役割ごとに表示
            if message["role"] == "assistant":  # AI応答
                if not message["content"]:  # 空応答
                    st.info("AI回答がありません（空回答）")  # 空応答表示
                else:  # 通常応答
                    st.success(message["content"])  # 成功表示
            else:  # ユーザーメッセージ
                st.markdown(message["content"])  # ユーザーメッセージ表示

# ===== ユーザーごとの履歴 永続化 =====


def _history_path(user_id: str) -> str:  # 履歴ファイルパス
    os.makedirs(cf.HISTORY_DIR, exist_ok=True)  # フォルダ作成
    safe = user_id.replace("/", "_").replace("\\",
                                             "_").strip() or "default"  # 安全なファイル名
    return os.path.join(cf.HISTORY_DIR, f"{safe}.json")  # 履歴ファイルパス


def _autosave_history():  # 履歴自動保存
    user_id = st.session_state.get("user_id", "") or "default"  # ユーザーID取得
    path = _history_path(user_id)  # 履歴ファイルパス
    with open(path, "w", encoding="utf-8") as f:  # ファイル書き込み
        json.dump(st.session_state.get("messages", []), f,
                  ensure_ascii=False, indent=2)  # JSON保存


def load_history(user_id: str):  # 履歴読み込み
    """指定ユーザーの履歴を読み込んで messages にセット"""
    path = _history_path(user_id)  # 履歴ファイルパス
    if os.path.exists(path):  # ファイルがあれば
        try:  # 読み込み
            with open(path, "r", encoding="utf-8") as f:  # ファイル読み込み
                st.session_state.messages = json.load(f)  # JSON読み込み
            _trim_history_inplace()  # トリム
            return True  # 読み込み成功
        except Exception:  # 読み込み失敗
            pass  # 失敗時の処理
    st.session_state.messages = []  # 履歴初期化
    return False  # 読み込み失敗
