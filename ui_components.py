import unicodedata
import streamlit as st
from langchain.schema import HumanMessage
from langchain_openai import ChatOpenAI
import config as cf


def render_header():  # ヘッダーを描画
    st.header(cf.APP_TITLE)  # アプリタイトル
    st.write(cf.DESCRIPTION)  # アプリ説明


def render_footer():  # フッターを描画
    st.text(cf.FOOTER_COPYRIGHT)  # コピーライト


def compose_error_message(message: str) -> str:  # エラーメッセージを構成
    return "\n".join([message, cf.ERROR_MSG_GENERAL])  # 一般的なエラーメッセージを追加


def _normalize(s: str) -> str:  # 文字列の正規化（検索用）
    # 例：全角→半角、英字小文字化、前後空白削除
    return unicodedata.normalize("NFKC", s or "").lower().strip()


def _pick_retriever(mode: str | None):  # modeに応じた retriever を返す
    """
    modeに応じた retriever を返す
    - None/その他: 'all'
    - 'faculty' | 'department' | 'research' | 'campus'
    """
    retrievers = st.session_state.get("retrievers", {})  # modeごとの retriever 辞書
    if mode in retrievers:  # modeに応じた retriever を返す
        return retrievers[mode]  # modeに応じた retriever を返す
    return retrievers.get("all")  # それ以外は 'all' を返す


def get_llm_response(user_message: str, mode: str | None = None):  # LLMの応答を取得
    """
    RAG: ①厳格 → ②最終フィルタ解除 → ③キーワードFallback（全モード対応）
    """
    logger = st.session_state.get("logger")  # ロガー取得
    llm = ChatOpenAI(model_name=cf.MODEL_NAME,
                     temperature=cf.TEMPERATURE)  # LLM初期化

    related_docs = []  # 初期化
    retriever = _pick_retriever(mode)  # modeに応じた retriever を取得
    query_norm = _normalize(user_message)  # 検索用に正規化

    if retriever is not None:  # retriever があれば
        try:  # 検索実行
            related_docs = retriever.invoke(user_message)  # user_message で検索
        except Exception as e:  # エラー処理
            if logger:  # ログ出力
                logger.error(f"Retriever error: {e}")  # エラーログ出力

    folder_map = {
        "faculty": cf.FOLDER_KEY_FACULTY,
        "department": cf.FOLDER_KEY_DEPARTMENT,
        "research": cf.FOLDER_KEY_RESEARCH,
        "campus": cf.FOLDER_KEY_CAMPUS,
    }
    key = folder_map.get(mode)
    if key and related_docs:
        related_docs = [
            d for d in related_docs
            if key in str((getattr(d, "metadata", {}) or {}).get("source", ""))
        ]

    if not related_docs and retriever is not None:  # 0件なら retriever があれば
        try:  # 3) 0件なら「最終フィルタを外して」もう一度だけ取得（同じ retriever から）
            related_docs = retriever.invoke(user_message)  # フィルタ外し
        except Exception:  # エラー処理
            pass  # 何もしない

    if not related_docs:  # それでも0件なら「キーワードFallback」（全モードで実施）
        raw = (st.session_state.get("raw_docs_by_bucket", {})
               or {}).get(mode or "all", [])  # modeごとの raw 辞書
        if not raw and mode:  # mode指定ありで raw がなければ
            raw = (st.session_state.get(
                "raw_docs_by_bucket", {}) or {}).get("all", [])  # 'all' の raw を使う
        hits = []  # ヒットしたドキュメント
        for d in raw:  # 全ドキュメントを走査
            text = _normalize(getattr(d, "page_content", ""))  # ドキュメント内容を正規化
            if query_norm and query_norm in text:  # 完全一致
                hits.append(d)  # ヒット追加
            else:  # 部分一致（簡易的にキーワードをいくつか設定）
                if "環境工学" in query_norm and ("環境工学" in text or "環境" in text):  # 環境工学関連
                    hits.append(d)  # ヒット追加
                # 例：奨学金→学費/支援など（簡易）
                if "奨学金" in query_norm and ("奨学金" in text or "支援" in text or "学費" in text):
                    hits.append(d)  # ヒット追加
            if len(hits) >= cf.TOP_K:  # 上限に達したら
                break  # ループ終了
        related_docs = hits  # ヒットを関連ドキュメントに設定

    if logger:  # ログ出力
        top_src = (related_docs[0].metadata.get(
            "source") if related_docs else "")  # 最初のドキュメントのソース
        logger.debug(
            f"[RAG] mode={mode} hits={len(related_docs)} top_source={top_src}")  # デバッグログ出力

    if not related_docs:
        label = {"faculty": "学部", "department": "学科",
                 "research": "研究室", "campus": "大学生活"}.get(mode, "データ")
        return {"answer": f"該当する{label}の情報が見つかりませんでした。検索語やデータ投入をご確認ください。"}

    context = "\n\n".join(
        [doc.page_content for doc in related_docs])  # コンテキストを結合
    prompt = f"""
あなたは教育機関向けの学内情報アシスタントです。
以下の文脈に基づき、関連する情報を整理・統合して、要点を簡潔にわかりやすくまとめてください。
文脈外の推測はしないでください。

【文脈】
{context}

【質問】
{user_message}

【回答】（箇条書きと短い要約を含めてください）
"""

    try:  # LLMへ投げる
        response = llm.invoke(prompt)  # LLM呼び出し
        st.session_state.chat_history.append(
            HumanMessage(content=user_message))  # ユーザーメッセージを履歴に追加
        st.session_state.chat_history.append(response)  # LLM応答を履歴に追加
        answer = getattr(response, "content", str(response))  # 応答内容取得
        if logger:  # ログ出力
            logger.debug(f"LLM回答: {answer}")  # デバッグログ出力
        return {"answer": answer}  # 応答を返す
    except Exception as e:  # エラー処理
        if logger:  # ログ出力
            logger.error(f"LLM単体回答エラー: {e}")  # エラーログ出力
        return {"answer": ""}  # 空応答を返す
