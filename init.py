"""
init.py
最初の画面読み込み時にのみ実行される初期化処理
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from uuid import uuid4
import sys
import unicodedata
import time
import re
import urllib.parse as urlparse
import urllib.robotparser as robotparser
from functools import lru_cache

from dotenv import load_dotenv
import streamlit as st

from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import WebBaseLoader

import config as cf

load_dotenv()  # .env読み込み


def initialize_app():  # アプリの初期化
    """画面読み込み時に実行する初期化処理"""
    init_session_state()  # セッションステートの初期化
    init_session_id()  # セッションIDの初期化
    init_logging()  # ログ出力の初期化
    init_retrievers()  # ベクトルDBの初期化


def init_logging():  # ログ出力の初期化
    """ログ出力の設定"""
    logger = logging.getLogger(cf.APP_LOGGER_NAME)  # ロガー取得
    logger.setLevel(logging.DEBUG)  # ログレベル設定
    logger.handlers.clear()  # 既存ハンドラ削除

    os.makedirs(cf.LOG_DIR, exist_ok=True)  # ログフォルダ作成
    log_file = os.path.join(cf.LOG_DIR, cf.LOG_FILE)  # ログファイルパス

    handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )  # 日次ローテート、7世代保存
    handler.suffix = "%Y%m%d"  # ログファイル名のサフィックス設定

    session_id = st.session_state.get("session_id", "unknown")  # セッションID取得
    formatter = logging.Formatter(
        f"[%(levelname)s] %(asctime)s line %(lineno)s, in %(funcName)s, session_id={session_id}: %(message)s"
    )  # フォーマット設定
    handler.setFormatter(formatter)  # フォーマッタ設定
    logger.addHandler(handler)  # ハンドラ設定

    console_handler = logging.StreamHandler(sys.stdout)  # コンソール出力用ハンドラ
    console_handler.setFormatter(formatter)  # フォーマッタ設定
    logger.addHandler(console_handler)  # コンソールにも出力

    st.session_state.logger = logger  # セッションステートにロガーを保存
    logger.info("Logging initialized.")  # ログ初期化完了ログ出力


def init_session_id():  # セッションIDの初期化
    """セッションIDの初期化"""
    if "session_id" not in st.session_state:  # 初回のみ生成
        st.session_state.session_id = str(uuid4())  # UUID4 形式
    logger = st.session_state.get("logger")  # ロガー取得
    if logger:  # ロガーが存在する場合
        logger.info(
            f"Session ID initialized: {st.session_state.session_id}")  # ログ出力
    print(f"Session ID: {st.session_state.session_id}")  # コンソール出力
    return st.session_state.session_id  # セッションIDを返す


def init_session_state():  # セッションステートの初期化
    """セッションステートの初期化"""
    st.session_state.setdefault("chat_history", [])  # チャット履歴
    st.session_state.setdefault("messages", [])  # 会話履歴
    st.session_state.setdefault("is_generating", False)  # 生成中フラグ
    st.session_state.setdefault("flow_step", 0)  # フローステップ
    # "faculty" | "department" | "research" | "campus"
    st.session_state.setdefault("flow_mode", None)
    st.session_state.setdefault("flow_is_generating", False)  # フロー生成中フラグ
    st.session_state.setdefault("flow_pending_q", "")  # フロー保留中の質問
    st.session_state.setdefault("user_id", "")  # ユーザーID


def init_retrievers():  # ベクトルDB初期化
    """ベクトルDB初期化（5コレクション: all/faculty/department/research/campus）"""
    logger = st.session_state.get("logger")  # ロガー取得

    if "retrievers" in st.session_state:  # すでに初期化済みなら何もしない
        if logger:  # ログ出力
            logger.info("Retrievers already initialized.")  # ログ出力
        return  # 初期化済み

    # データ読み込み
    docs_all = load_data_sources()  # 全ドキュメント取得
    if logger:  # ログ出力
        logger.debug(
            f"recursive_file_check結果: {len(docs_all)}件のドキュメントを取得")  # ログ出力

    for doc in docs_all:  # 文字列正規化・前処理
        doc.page_content = adjust_string(doc.page_content)  # 文字列調整
        for k in list(doc.metadata.keys()):  # メタデータの文字列正規化
            v = doc.metadata[k]  # 値取得
            doc.metadata[k] = v.strip() if isinstance(v, str) else v  # 正規化

    labels = [r"学部名[:：]", r"学科名[:：]", r"施設名[:：]",
              r"イベント名[:：]", r"証明書名[:：]"]  # 分割ラベル
    split_pattern = r"((?:" + "|".join(labels) + \
        r").+?)(?=\n(?:" + "|".join(labels) + r")|$)"  # 分割パターン

    splitter = CharacterTextSplitter(
        chunk_size=cf.CHUNK_SIZE, chunk_overlap=cf.CHUNK_OVERLAP, separator=cf.CHUNK_SEPARATOR
    )

    splitted = {
        "all": [],
        "faculty": [],
        "department": [],
        "research": [],
        "campus": [],
    }

    for doc in docs_all:  # ドキュメント分割と仕分け
        chunks = []  # 分割チャンク
        matches = re.findall(split_pattern, doc.page_content,
                             flags=re.DOTALL)  # パターンマッチ
        if matches:  # マッチしたらパターンで分割
            for m in matches:  # マッチ部分をチャンク化
                chunks.append(doc.__class__(page_content=m,  # チャンク化
                              metadata=doc.metadata.copy()))  # メタデータコピー
        else:  # マッチしなければ通常分割
            chunks.extend(splitter.split_documents([doc]))  # 通常分割

        splitted["all"].extend(chunks)  # all には常に投入

        src = str((doc.metadata or {}).get("source", ""))  # ソース取得
        if cf.FOLDER_KEY_FACULTY and cf.FOLDER_KEY_FACULTY in src:  # faculty
            splitted["faculty"].extend(chunks)  # 仕分け
        if cf.FOLDER_KEY_DEPARTMENT and cf.FOLDER_KEY_DEPARTMENT in src:  # department
            splitted["department"].extend(chunks)  # 仕分け
        if cf.FOLDER_KEY_RESEARCH and cf.FOLDER_KEY_RESEARCH in src:  # research
            splitted["research"].extend(chunks)  # 仕分け
        if cf.FOLDER_KEY_CAMPUS and cf.FOLDER_KEY_CAMPUS in src:  # campus
            splitted["campus"].extend(chunks)  # 仕分け

    if logger:  # ログ出力
        logger.debug(
            "分割後ドキュメント件数: " +
            ", ".join([f"{k}={len(v)}" for k, v in splitted.items()])  # ログ出力
        )

    embeddings = OpenAIEmbeddings(model=cf.EMBEDDING_MODEL_NAME)

    dbs = {}  # ベクトルDB辞書
    # Chromaに5コレクション作成（collection_name別）
    for name in ["all", "faculty", "department", "research", "campus"]:
        dbs[name] = Chroma.from_documents(
            documents=splitted[name] or [],
            embedding=embeddings,
            persist_directory=cf.VECTORSTORE_DIR,
            collection_name=name
        )

    def _make_kwargs(base_kwargs: dict, contains_key: str | None):  # フィルタ付き検索用kwargs作成
        if not contains_key:  # キーがなければフィルタなし
            return base_kwargs  # そのまま返す
        kw = dict(base_kwargs)  # コピー
        # source に特定フォルダ名が含まれているものだけ返す
        kw["filter"] = {"source": {"$contains": contains_key}}
        return kw  # 返す

    base = {"k": cf.TOP_K, "fetch_k": 15, "lambda_mult": 0.3}  # ベースkwargs
    retrievers = {
        "all": dbs["all"].as_retriever(
            search_type="mmr",
            search_kwargs=dict(base),
        ),
        "faculty": dbs["faculty"].as_retriever(
            search_type="mmr",
            search_kwargs=_make_kwargs(base, cf.FOLDER_KEY_FACULTY),
        ),
        "department": dbs["department"].as_retriever(
            search_type="mmr",
            search_kwargs=_make_kwargs(base, cf.FOLDER_KEY_DEPARTMENT),
        ),
        "research": dbs["research"].as_retriever(
            search_type="mmr",
            search_kwargs=_make_kwargs(base, cf.FOLDER_KEY_RESEARCH),
        ),
        "campus": dbs["campus"].as_retriever(
            search_type="mmr",
            search_kwargs=_make_kwargs(base, cf.FOLDER_KEY_CAMPUS),
        ),
    }
    st.session_state.retrievers = retrievers

    st.session_state.raw_docs_by_bucket = {  # Fallback用：分割後の生ドキュメントを保持
        "all": splitted["all"],  # all
        "faculty": splitted["faculty"],  # faculty
        "department": splitted["department"],  # department
        "research": splitted["research"],  # research
        "campus": splitted["campus"],  # campus
    }

    if logger:  # ログ出力
        logger.info(
            "Indexed docs: " +
            ", ".join([f"{k}={len(splitted[k])}" for k in splitted.keys()])
        )  # ログ出力


def load_data_sources():  # データソース読み込み
    """RAGの参照先となるデータソースの読み込み"""
    docs_all = []  # 全ドキュメント
    recursive_file_check(cf.RAG_ROOT_PATH, docs_all)  # フォルダ再帰走査

    if getattr(cf, "USE_WEB_SOURCES", False):  # Web取り込み（robots.txt 準拠、許可URLのみ）
        web_docs = load_web_sources_safe(
            getattr(cf, "WEB_URLS", []))  # Webドキュメント取得
        docs_all.extend(web_docs)  # 追加

    return docs_all  # 全ドキュメント返す


def recursive_file_check(path, docs_all):  # フォルダ再帰走査
    """対象フォルダを再帰走査して読み込み"""
    logger = st.session_state.get("logger")  # ロガー取得
    if os.path.isdir(path):  # フォルダなら
        for name in os.listdir(path):  # 中身走査
            full_path = os.path.join(path, name)  # フルパス
            recursive_file_check(full_path, docs_all)  # 再帰
    else:
        file_load(path, docs_all, logger)  # ファイル読み込み


def file_load(path, docs_all, logger=None):  # ファイル読み込み
    """個別ファイル読み込み"""
    file_extension = os.path.splitext(path)[1]  # 拡張子
    file_name = os.path.basename(path)  # ファイル名

    if file_extension in cf.ALLOWED_EXTENSIONS:  # 許可拡張子なら
        try:  # 読み込み
            loader = cf.ALLOWED_EXTENSIONS[file_extension](path)  # ローダー生成
            docs = loader.load()  # 読み込み
            docs_all.extend(docs)  # 追加
            if logger:  # ログ出力
                logger.debug(f"Loaded: {file_name} ({len(docs)} docs)")  # ログ出力
        except Exception as e:  # 読み込み失敗
            if logger:  # ログ出力
                logger.error(
                    f"Load failed: {file_name} ({file_extension}) -> {e}")  # ログ出力
    else:  # 非対応拡張子
        if logger:  # ログ出力
            logger.debug(
                f"Skipped (unsupported): {file_name} ({file_extension})")  # ログ出力


@lru_cache(maxsize=64)  # キャッシュ
def _get_robots_parser(base_url):  # robots.txt パーサ取得
    parts = urlparse.urlsplit(base_url)  # URL分解
    # robots.txt URL
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()  # パーサ生成
    rp.set_url(robots_url)  # URL設定
    try:  # 読み込み
        rp.read()  # 読み込み
    except Exception:  # 読み込み失敗
        pass  # 無視
    return rp  # 返す


def _can_fetch_url(url, user_agent):  # URLのクロール許可確認
    try:  # 確認
        parts = urlparse.urlsplit(url)  # URL分解
        base = f"{parts.scheme}://{parts.netloc}"  # ベースURL
        rp = _get_robots_parser(base)  # パーサ取得
        return bool(rp.can_fetch(user_agent, url))  # クロール許可確認
    except Exception:  # エラー時
        return False  # 不可


def load_web_sources_safe(urls):  # Webソース読み込み
    logger = st.session_state.get("logger")  # ロガー取得
    docs = []  # ドキュメントリスト
    if not urls:  # URLがなければ
        return docs  # 空のリストを返す

    ua = os.getenv("USER_AGENT") or cf.CRAWL_USER_AGENT  # User-Agent
    headers = {"User-Agent": ua}  # ヘッダ

    for url in urls:  # URL走査
        if not _can_fetch_url(url, headers["User-Agent"]):  # クロール不可なら
            if logger:  # ログ出力
                logger.info(f"[robots] Skipped (disallowed): {url}")  # ログ出力
            continue  # 次へ
        try:  # 読み込み
            loader = WebBaseLoader(
                web_paths=[url],
                requests_kwargs={"headers": headers, "timeout": 15},
                continue_on_failure=True,
                verify_ssl=True,
            )
            loaded = loader.load()
            docs.extend(loaded)
            if logger:  # ログ出力
                logger.info(
                    f"[web] Loaded {len(loaded)} docs from: {url}")  # ログ出力
            time.sleep(1.0)  # 負荷配慮
        except Exception as e:  # 読み込み失敗
            if logger:  # ログ出力
                logger.error(f"[web] Load failed: {url} -> {e}")  # ログ出力
    return docs  # ドキュメントリストを返す


def adjust_string(s):  # 文字列調整
    """Windows環境での文字化け回避のための軽い正規化"""
    if not isinstance(s, str):  # 文字列でなければ
        return s  # そのまま返す
    if sys.platform.startswith("win"):  # Windows環境なら
        s = unicodedata.normalize('NFC', s)  # 正規化
        s = s.encode("cp932", "ignore").decode("cp932")  # cp932でエンコード・デコード
        return s  # 返す
    return s  # そのまま返す
