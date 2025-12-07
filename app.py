import streamlit as st
import pandas as pd
import re
import time
import json
import google.generativeai as genai
from io import BytesIO

# ==========================================
# 設定頁面資訊
# ==========================================
st.set_page_config(
    page_title="太魯閣語構詞分析器 (AI Context-Aware)",
    page_icon="🎯",
    layout="wide"
)

# ==========================================
# API Key 設定區塊
# ==========================================
apiKey = None

try:
    if "GEMINI_API_KEY" in st.secrets:
        apiKey = st.secrets["GEMINI_API_KEY"]
except FileNotFoundError:
    pass 

if not apiKey:
    with st.sidebar:
        st.markdown("### ⚙️ 系統設定")
        user_api_input = st.text_input("請輸入 Google Gemini API Key", type="password")
        if user_api_input:
            apiKey = user_api_input
        st.caption("ℹ️ 此版本極度依賴 AI 進行語意判讀，請務必輸入 API Key。")
        st.markdown("---")

with st.sidebar:
    if apiKey:
        st.success(f"✅ API Key 已載入")
        st.caption("🚀 模型：gemini-2.5-flash (語境精準模式)")
    else:
        st.warning("⚠️ 未偵測到 API Key")

# ==========================================
# 1. 核心字典庫 (作為備用資料庫)
# ==========================================
# 雖然我們依賴 AI，但保留字典可以在 AI 失敗時作為保險
@st.cache_data(persist=True)
def get_dictionary():
    return {
        "ka": {"morph": "ka", "gloss": "主格", "meaning": "(主格標記)"},
        "ni": {"morph": "ni", "gloss": "連接詞", "meaning": "和/與"},
        "o": {"morph": "o", "gloss": "主題", "meaning": "(主題標記)"},
        "do": {"morph": "do", "gloss": "助詞", "meaning": "(強調/時間)"},
        "ga": {"morph": "ga", "gloss": "助詞", "meaning": "(特定)"},
        # ... (您可以繼續保留舊有的字典，這裡省略以節省篇幅)
    }
DICTIONARY = get_dictionary()

# ==========================================
# 2. AI 核心功能：整句語境分析 (Context-Aware Glossing)
# ==========================================
@st.cache_data(show_spinner=False)
def call_ai_sentence_analysis(sentence, api_key):
    """
    輸入：整句太魯閣語 (例如 "Mha ku qmita tnkuyan mu.")
    輸出：一個包含每個字詳細分析的 JSON List
    """
    if not api_key: return None

    try:
        genai.configure(api_key=api_key)
        # 設定回傳格式為 JSON，確保程式能精準讀取
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})

        prompt = f"""
        你是一位精通太魯閣語(Truku/Seediq)的語言學家。
        請對以下句子進行「逐字構詞標註 (Interlinear Glossing)」。
        
        句子："{sentence}"

        請仔細分析這句話的語法結構與上下文，然後回傳一個 JSON 陣列 (List)。
        陣列中的每一個物件代表句子裡的一個單字(Word)，必須包含以下欄位：
        
        1. "original": 原字 (包含標點符號請獨立切分)
        2. "morph": 構詞分析 (例如 m-ekan, s<m>ruwa, root-an)。如果是單純名詞則維持原樣。
        3. "gloss": 語法標記 (請用繁體中文，如：主事焦點、主格、屬格、未來、完成)。
        4. "meaning": **重點**：請提供該字在「這個句子中」的確切中文意思。不要給字典原意，要給上下文意。

        範例輸出格式：
        [
            {{"original": "Mha", "morph": "mha", "gloss": "未來", "meaning": "將要"}},
            {{"original": "ku", "morph": "ku", "gloss": "1S.主格", "meaning": "我"}},
            {{"original": "qmita", "morph": "q<m>ita", "gloss": "主事焦點-看", "meaning": "看"}},
            ...
        ]
        
        請確保回傳的是標準 JSON 格式，不要有 Markdown 標記。
        """
        
        response = model.generate_content(prompt)
        return json.loads(response.text)
    
    except Exception as e:
        return {"error": str(e)}

# 翻譯整句 (輔助用)
@st.cache_data(show_spinner=False)
def call_ai_translation(text, api_key):
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"請將太魯閣語句子「{text}」翻譯成通順的繁體中文，直接給出翻譯結果即可。"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "(翻譯失敗)"

# ==========================================
# 3. 輔助函式：斷句
# ==========================================
def split_sentences(text):
    # 針對半型標點斷句
    pattern = r'([.?!]+)' 
    parts = re.split(pattern, text)
    sentences = []
    temp_text = ""
    for part in parts:
        if not part: continue 
        if re.match(pattern, part):
            temp_text += part
            sentences.append(temp_text.strip())
            temp_text = "" 
        else:
            temp_text += part
    if temp_text.strip():
        sentences.append(temp_text.strip())
    return sentences

# ==========================================
# 介面邏輯
# ==========================================

st.title("太魯閣語構詞分析器 (AI Context-Aware)")
st.caption("🚀 語境感知版：利用 AI 分析整句上下文，解決單字意思不準確的問題。")
st.markdown("---")

if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

def set_example_text(text):
    st.session_state["user_input"] = text

# 範例
ex1_text = "Mtalux bi ka hidaw. Mring kana ka hiyi mu."
ex2_text = "Bhangan ka kari o meiyah ka bgihur paru msa."
ex3_text = "Mlatat su o iya bi snguhi madas bubung."

col1, col2 = st.columns([3, 1])
with col1:
    input_text = st.text_area("請輸入句子 (族語或中文)", height=100, 
                              placeholder="支援多句輸入，例如：Mha ku qmita tnkuyan mu.", 
                              key="user_input")
with col2:
    st.write("範例：")
    st.button("範例 1", on_click=set_example_text, args=(ex1_text,))
    st.button("範例 2", on_click=set_example_text, args=(ex2_text,))
    st.button("範例 3", on_click=set_example_text, args=(ex3_text,))

# 用來暫存 AI 分析結果 (如果是多句，最後要合併下載)
if "analysis_results" not in st.session_state:
    st.session_state["analysis_results"] = []

# 分析按鈕
if st.button("開始精準分析", type="primary"):
    input_content = st.session_state["user_input"]
    
    if not input_content:
        st.warning("請輸入文字")
    else:
        # 清空舊結果
        st.session_state["analysis_results"] = []
        all_csv_data = [["Line", "Content"]] # CSV Header

        # 1. 斷句
        sentence_list = split_sentences(input_content)
        
        # 2. 逐句處理
        for idx, single_sentence in enumerate(sentence_list):
            if len(sentence_list) > 1:
                st.markdown(f"#### 句子 {idx + 1}")

            with st.spinner(f"正在進行語境分析... ({idx+1}/{len(sentence_list)})"):
                
                # 判斷是否為中文 (如果是中文，先翻成族語)
                is_chinese = any("\u4e00" <= char <= "\u9fff" for char in single_sentence)
                source_sentence = single_sentence
                
                if is_chinese:
                    if not apiKey:
                        st.error("需要 API Key 才能處理中文。")
                        st.stop()
                    # 呼叫翻譯 API
                    translated = call_ai_translation(f"請將中文 '{single_sentence}' 翻譯成太魯閣語", apiKey)
                    if translated:
                        # 顯示翻譯過程
                        st.info(f"中文翻譯偵測： {single_sentence}  ➡️  {translated}")
                        source_sentence = translated
                    else:
                        st.error("翻譯失敗")
                        st.stop()

                # --- 核心：呼叫 AI 進行整句語境分析 ---
                if apiKey:
                    # 這是最重要的一步：直接問 AI 這句話每個字的意思
                    ai_analysis_json = call_ai_sentence_analysis(source_sentence, apiKey)
                    
                    if isinstance(ai_analysis_json, list):
                        # AI 成功回傳 List
                        analyzed_words = ai_analysis_json
                        
                        # 順便取得整句翻譯 (可以直接用上面的，或是再問一次更準的)
                        full_translation = call_ai_translation(source_sentence, apiKey)
                    else:
                        # AI 回傳錯誤
                        st.error(f"AI 分析發生錯誤: {ai_analysis_json}")
                        analyzed_words = [{"original": w, "morph": "???", "gloss": "???", "meaning": "???"} for w in source_sentence.split()]
                        full_translation = "(分析失敗)"
                else:
                    # 沒有 API Key 的降級處理 (只查字典)
                    st.error("請輸入 API Key 以獲得精準語境分析。目前僅顯示基礎字典匹配。")
                    analyzed_words = []
                    for w in source_sentence.split():
                        clean_w = re.sub(r'[.,?!]', '', w).lower()
                        d = DICTIONARY.get(clean_w, {"morph": w, "gloss": "???", "meaning": "???"})
                        analyzed_words.append({"original": w, "morph": d["morph"], "gloss": d["gloss"], "meaning": d["meaning"]})
                    full_translation = "(無 API Key)"

                # --- 顯示結果 (四行標註) ---
                # 準備資料
                line1 = [w.get('original', '') for w in analyzed_words]
                line2 = [w.get('morph', '') for w in analyzed_words]
                line3 = [w.get('gloss', '') for w in analyzed_words]
                # 這裡的 Meaning 來自 AI 的語境分析，不再是字典死板的意思
                line4_words = [w.get('meaning', '') for w in analyzed_words] 
                
                # 顯示 HTML
                html_output = f"""
                <div style="font-family: monospace; font-size: 16px; line-height: 1.8; background-color: #f8f9fa; color: #1f2937; padding: 20px; border-radius: 10px; margin-bottom: 20px; overflow-x: auto;">
                    <div style="margin-bottom: 8px; white-space: nowrap;"><span style="color: #e11d48; font-weight: bold; margin-right: 10px;">● 原句</span> {' '.join(line1)}</div>
                    <div style="margin-bottom: 8px; white-space: nowrap;"><span style="color: #2563eb; font-weight: bold; margin-right: 10px;">● 構詞</span> {' '.join(line2)}</div>
                    <div style="margin-bottom: 8px; white-space: nowrap;"><span style="color: #059669; font-weight: bold; margin-right: 10px;">● 詞法</span> {' '.join(line3)}</div>
                    <div style="margin-bottom: 8px; white-space: nowrap;"><span style="color: #7c3aed; font-weight: bold; margin-right: 10px;">● 釋義</span> {' '.join(line4_words)}</div>
                    <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #d1d5db; font-weight: bold;">
                        <span style="color: #d97706;">● 整句</span> {full_translation}
                    </div>
                </div>
                """
                st.markdown(html_output, unsafe_allow_html=True)

                # 收集 CSV 資料
                all_csv_data.append([f"Sentence {idx+1} - Line 1 (Original)", ' '.join(line1)])
                all_csv_data.append([f"Sentence {idx+1} - Line 2 (Morph)", ' '.join(line2)])
                all_csv_data.append([f"Sentence {idx+1} - Line 3 (Gloss)", ' '.join(line3)])
                all_csv_data.append([f"Sentence {idx+1} - Line 4 (Meaning)", ' '.join(line4_words)]) # 這是單字意思
                all_csv_data.append([f"Sentence {idx+1} - Translation", full_translation]) # 這是整句翻譯
                all_csv_data.append(["---", "---"])

        # 3. 匯出按鈕
        df_export = pd.DataFrame(all_csv_data)
        csv = df_export.to_csv(index=False, header=False).encode('utf-8-sig')
        
        st.download_button(
            label="📥 匯出 Excel (CSV)",
            data=csv,
            file_name='truku_smart_analysis.csv',
            mime='text/csv',
        )

st.markdown("---")
st.caption("資料來源：AI 上下文語境分析 (Gemini 2.5) | 設計用途：族語教學與語料保存")
