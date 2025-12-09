import streamlit as st
import pandas as pd
import re
import time
import json
import os
import google.generativeai as genai
from io import BytesIO

# ==========================================
# 設定頁面資訊
# ==========================================
st.set_page_config(
    page_title="太魯閣語構詞分析器 (AI Pro)",
    page_icon="📖",
    layout="wide"
)

# ==========================================
# API Key 設定區塊
# ==========================================
apiKey = None

# 嘗試從 secrets 讀取，若無則顯示側邊欄輸入
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
        st.caption("ℹ️ 若無 API Key，僅能進行詞法拆解，無法使用整句翻譯。")
        st.markdown("---")

with st.sidebar:
    if apiKey:
        st.success(f"✅ API Key 已載入")
    else:
        st.warning("⚠️ 未偵測到 API Key")

# ==========================================
# 1. 核心字典庫 (升級版：讀取 Excel)
# ==========================================
@st.cache_data(persist=True)
def load_excel_dictionary(filepath):
    """
    讀取 truku_dictionary_final.xlsx 並轉換為 App 能用的格式
    """
    dictionary = {}
    
    # 預設的一些基礎單字 (防呆用)
    base_dict = {
        "ka": {"morph": "ka", "gloss": "主格", "meaning": "(主格標記)"},
        "ni": {"morph": "ni", "gloss": "連接詞", "meaning": "和/與"},
    }
    dictionary.update(base_dict)

    if not os.path.exists(filepath):
        st.error(f"❌ 找不到辭典檔：{filepath}。請確保檔案已上傳。")
        return dictionary

    try:
        df = pd.read_excel(filepath)
        # 自動偵測欄位 (防呆)
        word_col = next((c for c in df.columns if 'Word' in c or 'word' in c), None)
        gloss_col = next((c for c in df.columns if 'Gloss' in c or 'gloss' in c), None)
        
        if word_col and gloss_col:
            for _, row in df.iterrows():
                word = str(row[word_col]).strip().lower()
                gloss = str(row[gloss_col]).strip()
                
                # 如果 Gloss 是空白或 ???，就略過或標記
                if gloss == "nan" or gloss == "???" or not gloss:
                    continue

                # 將 Excel 資料存入字典
                # 注意：因為辭典檔只有 Word 和 Gloss，我們先把 Gloss 同時當作 Meaning
                dictionary[word] = {
                    "morph": word,       # 辭典檔目前沒有構詞拆解，暫時用原詞
                    "gloss": gloss,
                    "meaning": gloss     # 暫時用 gloss 當作 meaning
                }
        else:
            st.error("❌ 辭典檔欄位名稱不符 (需要 Word 和 Gloss)")
            
    except Exception as e:
        st.error(f"讀取辭典失敗: {e}")

    return dictionary

# --- 這裡設定您的辭典檔名 ---
DICT_FILE = 'truku_dictionary_final.xlsx'
DICTIONARY = load_excel_dictionary(DICT_FILE)

# 顯示載入狀況
with st.sidebar:
    st.info(f"📚 已載入辭典：{len(DICTIONARY)} 詞條")

# ==========================================
# 2. 構詞規則引擎 (未查到單字時的猜測)
# ==========================================
def analyze_morphology(word):
    analysis = {"morph": word, "gloss": "???", "meaning": ""}
    
    # 常用前綴規則
    if re.match(r'^m[a-z]+', word) and not word.startswith("ma"):
        if word.startswith("me"):
            root = word[2:]
            return {"morph": f"me-{root}", "gloss": "主事焦點-", "meaning": "(動詞)"}
        elif word.startswith("m"):
            root = word[1:]
            if any(char in "aeiou" for char in root):
                return {"morph": f"m-{root}", "gloss": "主事焦點-", "meaning": "(動詞)"}
    
    # 中綴 -m-
    if len(word) > 3 and word[1] == 'm' and word[2] in "aeiou":
         root = word[0] + word[2:]
         return {"morph": f"{word[0]}<m>{word[2:]}", "gloss": "<主事焦點>", "meaning": "(動詞)"}

    # 中綴 -n- (完成貌)
    if len(word) > 3 and word[1] == 'n' and word[2] in "aeiou":
         root = word[0] + word[2:]
         return {"morph": f"{word[0]}<n>{word[2:]}", "gloss": "<完成貌>", "meaning": "(動詞)"}
    
    # 常用後綴
    if word.endswith("un"):
        root = word[:-2]
        return {"morph": f"{root}-un", "gloss": "-受事焦點", "meaning": "(被動/未來)"}
    if word.endswith("an"):
        root = word[:-2]
        return {"morph": f"{root}-an", "gloss": "-處所焦點", "meaning": "(處所/過去)"}
    if word.endswith("i"):
        root = word[:-1]
        return {"morph": f"{root}-i", "gloss": "-祈使", "meaning": "(命令)"}

    return analysis

# ==========================================
# 3. AI 翻譯 API
# ==========================================
@st.cache_data(show_spinner=False)
def call_ai_translation(text, target_lang, gloss_context, api_key):
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        if target_lang == 'truku':
            prompt = f"請將以下中文句子翻譯成太魯閣族語(Truku)。直接給出翻譯後的族語句子即可，不要包含其他解釋或拼音。\n句子：{text}"
        else:
            prompt = f"""
            你是一個精通太魯閣語(Truku)與中文的語言學家。請進行以下翻譯任務：
            1. **結構對應**：參考提供的 [詞法分析] (Gloss)。
            2. **直譯**：先進行詞對詞直譯。
            3. **語意優化**：將直譯結果調整為通順中文。

            原文：{text}
            詞法分析參考：{gloss_context}

            請直接輸出翻譯結果，不要包含任何解釋。
            """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        return f"ERROR: {str(e)}"

# ==========================================
# 4. 輔助函式：切分句子
# ==========================================
def split_sentences(text):
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

st.title("太魯閣語構詞分析器 (Pro)")
st.markdown("---")

if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

def set_example_text(text):
    st.session_state["user_input"] = text

col1, col2 = st.columns([3, 1])

with col1:
    input_text = st.text_area("請輸入句子 (族語或中文)", height=100, 
                              placeholder="支援多句輸入，例如：Mtalux bi ka hidaw.", 
                              key="user_input")

with col2:
    st.write("測試範例：")
    st.button("範例 1: 天氣", on_click=set_example_text, args=("Mtalux bi ka hidaw.",))
    st.button("範例 2: 對話", on_click=set_example_text, args=("Ima hangan na ka qbsuran su kuyuh?",))

# 分析按鈕
if st.button("開始分析", type="primary"):
    input_content = st.session_state["user_input"]
    
    if not input_content:
        st.warning("請輸入文字")
    else:
        # --- 切分句子 ---
        sentence_list = split_sentences(input_content)
        
        # 準備 CSV 匯出資料
        all_csv_data = []
        all_csv_data.append(["Line", "Content"])

        # 逐句處理
        for idx, single_sentence in enumerate(sentence_list):
            
            if len(sentence_list) > 1:
                st.markdown(f"#### 句子 {idx + 1}")

            with st.spinner(f"分析中... ({idx+1}/{len(sentence_list)})"):
                # 1. 判斷語言模式
                is_chinese = any("\u4e00" <= char <= "\u9fff" for char in single_sentence)
                
                source_text = single_sentence
                translation_text = ""

                # 2. 中文 -> 族語 (AI)
                if is_chinese:
                    if not apiKey:
                        st.error("需要 API Key 才能翻譯中文。")
                        st.stop()
                    
                    ai_result = call_ai_translation(source_text, 'truku', "", apiKey)
                    if ai_result and not ai_result.startswith("ERROR:"):
                        translation_text = source_text
                        source_text = ai_result
                    else:
                        translation_text = "(翻譯失敗)"

                # 3. 構詞分析 (核心升級：查 Excel 字典)
                clean_text = re.sub(r'[.,?!;:，。？！；：]', '', source_text).lower()
                raw_words = source_text.split()
                
                analyzed_words = []
                for word in raw_words:
                    # 去除標點並轉小寫以進行查表
                    clean_word = re.sub(r'[.,?!;:，。？！；：]', '', word).lower()
                    
                    # 優先查表
                    if clean_word in DICTIONARY:
                        data = DICTIONARY[clean_word]
                        # 因為 Excel 字典沒紀錄 morph 拆解，這邊 morph 暫時顯示原詞
                        # 如果您未來有更精細的資料，可以再調整
                        analyzed_words.append({"original": word, "morph": word, "gloss": data["gloss"], "meaning": data["meaning"]})
                    else:
                        # 查不到則使用規則猜測
                        guess = analyze_morphology(clean_word)
                        analyzed_words.append({"original": word, "morph": guess["morph"], "gloss": guess["gloss"], "meaning": guess["meaning"]})

                # 4. 族語 -> 中文 (AI)
                if not is_chinese:
                    # 組合 Gloss 給 AI 參考，讓翻譯更準
                    gloss_context = " ".join([f"{w['original']}({w['gloss']})" for w in analyzed_words if w['gloss'] != "???"])
                    
                    if apiKey:
                        ai_result = call_ai_translation(source_text, 'chinese', gloss_context, apiKey)
                        if ai_result and not ai_result.startswith("ERROR:"):
                             translation_text = ai_result
                        else:
                             translation_text = "(翻譯失敗)"
                    else:
                        translation_text = "(未設定 API Key)"

                # 5. 顯示結果 (四行對照)
                html_output = f"""
                <div style="font-family: monospace; font-size: 16px; line-height: 1.8; background-color: #f8f9fa; color: #1f2937; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div style="margin-bottom: 8px;"><span style="color: #e11d48; font-weight: bold;">word:</span> {' '.join([w['original'] for w in analyzed_words])}</div>
                    <div style="margin-bottom: 8px;"><span style="color: #2563eb; font-weight: bold;">gloss:</span> {' '.join([w['gloss'] for w in analyzed_words])}</div>
                    <div style="margin-top: 12px; font-weight: bold; border-top: 1px solid #e5e7eb; padding-top: 8px;"><span style="color: #d97706;">Trans:</span> {translation_text}</div>
                </div>
                """
                st.markdown(html_output, unsafe_allow_html=True)

                # 收集 CSV
                all_csv_data.append([f"S{idx+1}-L1", ' '.join([w['original'] for w in analyzed_words])])
                all_csv_data.append([f"S{idx+1}-L2", ' '.join([w['gloss'] for w in analyzed_words])])
                all_csv_data.append([f"S{idx+1}-L3", translation_text])
                all_csv_data.append(["---", "---"])

        # 6. 匯出功能
        df_export = pd.DataFrame(all_csv_data)
        csv = df_export.to_csv(index=False, header=False).encode('utf-8-sig')
        
        st.download_button(
            label="匯出 Excel (CSV)",
            data=csv,
            file_name='truku_analysis_result.csv',
            mime='text/csv',
        )

st.markdown("---")
st.caption("資料來源：自動化 Excel 辭典庫 | 設計用途：族語教學與語料保存")
