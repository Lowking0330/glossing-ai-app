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
    page_title="太魯閣語構詞分析器 (AI Auto-Glossing)",
    page_icon="🧠",
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
        st.caption("ℹ️ 若無 API Key，僅能進行基礎詞法拆解，無法使用 AI 自動補字。")
        st.markdown("---")

with st.sidebar:
    if apiKey:
        st.success(f"✅ API Key 已載入")
        st.caption("🚀 模型：gemini-2.5-flash (AI 自動補字開啟)")
    else:
        st.warning("⚠️ 未偵測到 API Key")

# ==========================================
# 1. 核心字典庫 (基礎資料)
# ==========================================
@st.cache_data(persist=True)
def get_dictionary():
    return {
        # --- 原有單字 (僅保留部分範例，AI 會處理剩下的) ---
        "tmkuy": {"morph": "t<m>kuy", "gloss": "<主事焦點>種", "meaning": "種植"},
        "tnkuyan": {"morph": "tnkuy-an", "gloss": "田", "meaning": "田地"},
        "masu": {"morph": "masu", "gloss": "小米", "meaning": "小米"},
        "ka": {"morph": "ka", "gloss": "主格", "meaning": "(主格標記)"},
        "ni": {"morph": "ni", "gloss": "連接詞", "meaning": "和/與"},
        "o": {"morph": "o", "gloss": "主題", "meaning": "(主題標記)"},
        "do": {"morph": "do", "gloss": "助詞", "meaning": "(強調/時間)"},
        "ga": {"morph": "ga", "gloss": "助詞", "meaning": "(特定)"},
        "hug": {"morph": "hug", "gloss": "疑問詞", "meaning": "嗎"},
        "da": {"morph": "da", "gloss": "語尾助詞", "meaning": "了"},
        "saw": {"morph": "saw", "gloss": "像", "meaning": "像/如此"},
        "kiya": {"morph": "kiya", "gloss": "那", "meaning": "那/所以"},
        "kika": {"morph": "kika", "gloss": "連接詞", "meaning": "所以/就是"},
        "nasi": {"morph": "nasi", "gloss": "連接詞", "meaning": "如果"},
        "ana": {"morph": "ana", "gloss": "無定詞", "meaning": "雖然/即使"},
        "ida": {"morph": "ida", "gloss": "助動詞", "meaning": "一定/仍然"},
        "ini": {"morph": "ini", "gloss": "否定", "meaning": "不/沒有"},
        "aji": {"morph": "aji", "gloss": "否定", "meaning": "不是/不要"},
        "uxay": {"morph": "uxay", "gloss": "否定", "meaning": "不是"},
        "iya": {"morph": "iya", "gloss": "否定祈使", "meaning": "別/不要"},
        "ungat": {"morph": "ungat", "gloss": "否定存在", "meaning": "沒有"},
        "niqan": {"morph": "niqan", "gloss": "存在", "meaning": "有"},
        "wada": {"morph": "wada", "gloss": "完成貌.助動", "meaning": "已經/去"},
        "gisu": {"morph": "gisu", "gloss": "進行貌.助動", "meaning": "正在(近)"},
        "gaga": {"morph": "gaga", "gloss": "進行貌.助動", "meaning": "正在(遠)/在那裡"},
        "mha": {"morph": "mha", "gloss": "未來.助動", "meaning": "將"},
        "naa": {"morph": "naa", "gloss": "助動詞", "meaning": "應該"},
        "ku": {"morph": "ku", "gloss": "1S.主格", "meaning": "我"},
        "su": {"morph": "su", "gloss": "2S.主格/屬格", "meaning": "你/你的"},
        "mu": {"morph": "mu", "gloss": "1S.屬格", "meaning": "我的"},
        "na": {"morph": "na", "gloss": "3S.屬格", "meaning": "他的/尚未"},
        "ta": {"morph": "ta", "gloss": "1PL.包含.主格", "meaning": "我們(包含)"},
        "nami": {"morph": "nami", "gloss": "1PL.排除.主格/屬格", "meaning": "我們(排除)"},
        "namu": {"morph": "namu", "gloss": "2PL.主格/屬格", "meaning": "你們"},
        "deha": {"morph": "deha", "gloss": "3PL.主格/屬格", "meaning": "他們/二"},
        "yaku": {"morph": "yaku", "gloss": "1S.主格(獨立)", "meaning": "我"},
        "isu": {"morph": "isu", "gloss": "2S.主格(獨立)", "meaning": "你"},
        "hiya": {"morph": "hiya", "gloss": "3S.主格(獨立)", "meaning": "他/她/那裡"},
        "kenan": {"morph": "kenan", "gloss": "1S.斜格", "meaning": "對我/被我"},
        "sunan": {"morph": "sunan", "gloss": "2S.斜格", "meaning": "對你/被你"},
        "menan": {"morph": "menan", "gloss": "1PL.排除.斜格", "meaning": "我們"},
        "niyi": {"morph": "niyi", "gloss": "指示", "meaning": "這/這個"}
    }
DICTIONARY = get_dictionary()

# ==========================================
# 2. 構詞規則引擎 (Rule-Based)
# ==========================================
def analyze_morphology_rule(word):
    # 這是原本的規則引擎，當作備用
    analysis = {"morph": word, "gloss": "???", "meaning": ""}
    
    # 簡單的前綴規則範例
    if re.match(r'^m[a-z]+', word) and not word.startswith("ma"):
        if word.startswith("me"):
            return {"morph": f"me-{word[2:]}", "gloss": "主事焦點-", "meaning": "(動詞)"}
        elif word.startswith("m"):
            if any(char in "aeiou" for char in word[1:]):
                return {"morph": f"m-{word[1:]}", "gloss": "主事焦點-", "meaning": "(動詞)"}
    
    if word.endswith("an"):
        return {"morph": f"{word[:-2]}-an", "gloss": "-處所焦點", "meaning": "(處所/名詞)"}
    
    return analysis

# ==========================================
# 3. AI 服務整合 (翻譯 + 自動字典)
# ==========================================

# A. 句子翻譯
@st.cache_data(show_spinner=False)
def call_ai_translation(text, target_lang, gloss_context, api_key):
    if not api_key: return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        if target_lang == 'truku':
            prompt = f"請將中文「{text}」翻譯成太魯閣族語(Truku)。直接給出翻譯後的句子。"
        else:
            prompt = f"""
            你是一個語言學家。請將這句太魯閣語(Truku)翻譯成中文。
            參考詞法：{gloss_context}
            原文：{text}
            只需輸出翻譯結果，不要解釋。
            """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "(翻譯服務暫時無法使用)"

# B. [新功能] AI 批量單字查詢 (Auto-Glossing)
@st.cache_data(show_spinner=False)
def call_ai_dictionary_batch(words_list, api_key):
    """
    輸入: ['word1', 'word2']
    輸出: JSON 字串，包含每個字的 morph, gloss, meaning
    """
    if not api_key or not words_list: return "{}"
    
    try:
        genai.configure(api_key=api_key)
        # 設定回應為 JSON 模式 (Gemini 2.5/Pro 支援)
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
        
        prompt = f"""
        你是一個太魯閣語(Truku)字典專家。
        請分析以下單字列表：{words_list}
        
        請回傳一個 JSON 物件，格式如下：
        {{
            "單字原形": {{
                "morph": "構詞分析 (例如 m-ekan)", 
                "gloss": "詞法標記 (例如 主事焦點-吃)", 
                "meaning": "中文意思 (例如 吃)"
            }}
        }}
        
        注意：
        1. "morph" 欄位請標示詞綴切分 (如 m-root, root-an)。
        2. "gloss" 欄位請使用語言學簡寫或中文標記。
        3. 如果不確定，請根據太魯閣語構詞規則進行最合理的推測。
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"AI 字典查詢失敗: {e}")
        return "{}"

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

st.title("太魯閣語構詞分析器 (AI Auto-Glossing)")
st.markdown("---")

if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

# 範例按鈕回呼
def set_example_text(text):
    st.session_state["user_input"] = text

# 定義範例 (包含字典裡沒有的字，測試 AI 能力)
ex1_text = "Mtalux bi ka hidaw. Mring kana ka hiyi mu."
ex2_text = "Bhangan ka kari o meiyah ka bgihur paru msa."
ex3_text = "Mlatat su o iya bi snguhi madas bubung."

col1, col2 = st.columns([3, 1])
with col1:
    input_text = st.text_area("請輸入句子 (族語或中文)", height=100, 
                              placeholder="支援多句輸入，例如：Sentence 1. Sentence 2.", 
                              key="user_input")
with col2:
    st.write("範例 (測試 AI 補字)：")
    st.button("範例 1", on_click=set_example_text, args=(ex1_text,))
    st.button("範例 2", on_click=set_example_text, args=(ex2_text,))
    st.button("範例 3", on_click=set_example_text, args=(ex3_text,))

# 用來收集本次 AI 查到的新字，供側邊欄下載
if "ai_generated_dict" not in st.session_state:
    st.session_state["ai_generated_dict"] = {}

# 分析按鈕
if st.button("開始分析", type="primary"):
    input_content = st.session_state["user_input"]
    
    if not input_content:
        st.warning("請輸入文字")
    else:
        # 1. 預處理：找出整段文章中「字典沒有的字」
        all_words_in_text = re.findall(r"\b[a-zA-Z]+\b", input_content.lower())
        unknown_words = []
        for w in all_words_in_text:
            if w not in DICTIONARY and w not in st.session_state["ai_generated_dict"]:
                unknown_words.append(w)
        
        # 2. 如果有生字，呼叫 AI 批量查詢 (Batch AI Lookup)
        if unknown_words and apiKey:
            with st.status("🔍 發現陌生單字，正在詢問 AI 字典...", expanded=True) as status:
                st.write(f"正在查詢：{', '.join(set(unknown_words))}")
                
                # 呼叫 AI
                ai_dict_json = call_ai_dictionary_batch(list(set(unknown_words)), apiKey)
                
                try:
                    # 解析 JSON 並存入 session state
                    new_entries = json.loads(ai_dict_json)
                    st.session_state["ai_generated_dict"].update(new_entries)
                    status.update(label="✅ AI 字典更新完成！", state="complete", expanded=False)
                except json.JSONDecodeError:
                    st.error("AI 回傳格式錯誤，將使用規則引擎備援。")

        # 3. 開始逐句分析
        sentence_list = split_sentences(input_content)
        all_csv_data = [["Line", "Content"]]

        for idx, single_sentence in enumerate(sentence_list):
            if len(sentence_list) > 1:
                st.markdown(f"#### 句子 {idx + 1}")

            with st.spinner(f"分析中... ({idx+1}/{len(sentence_list)})"):
                # 判斷語言
                is_chinese = any("\u4e00" <= char <= "\u9fff" for char in single_sentence)
                source_text = single_sentence
                translation_text = ""

                # 中文 -> 族語
                if is_chinese:
                    if not apiKey:
                        st.error("需要 API Key。")
                        st.stop()
                    source_text = call_ai_translation(source_text, 'truku', "", apiKey)
                    translation_text = single_sentence

                # 構詞分析 (結合 內建字典 + AI 字典 + 規則)
                clean_text = re.sub(r'[.,?!;:，。？！；：]', '', source_text).lower()
                raw_words = source_text.split()
                analyzed_words = []

                for word in raw_words:
                    clean_word = re.sub(r'[.,?!;:，。？！；：]', '', word).lower()
                    
                    # 優先序 1: 內建字典
                    if clean_word in DICTIONARY:
                        d = DICTIONARY[clean_word]
                        analyzed_words.append({"original": word, "morph": d["morph"], "gloss": d["gloss"], "meaning": d["meaning"]})
                    
                    # 優先序 2: AI 剛剛生成的字典 (Session State)
                    elif clean_word in st.session_state["ai_generated_dict"]:
                        d = st.session_state["ai_generated_dict"][clean_word]
                        analyzed_words.append({"original": word, "morph": d.get("morph", clean_word), "gloss": d.get("gloss", "AI"), "meaning": d.get("meaning", "?")})
                    
                    # 優先序 3: 規則引擎 (最後手段)
                    else:
                        guess = analyze_morphology_rule(clean_word)
                        analyzed_words.append({"original": word, "morph": guess["morph"], "gloss": guess["gloss"], "meaning": guess["meaning"]})

                # 族語 -> 中文
                if not is_chinese:
                    gloss_context = " ".join([f"{w['original']}({w['gloss']}/{w['meaning']})" for w in analyzed_words])
                    if apiKey:
                        translation_text = call_ai_translation(source_text, 'chinese', gloss_context, apiKey)
                    else:
                        translation_text = "(未設定 API Key)"

                # 顯示結果
                html_output = f"""
                <div style="font-family: monospace; font-size: 16px; line-height: 1.8; background-color: #f8f9fa; color: #1f2937; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <div style="margin-bottom: 8px;"><span style="color: #e11d48; font-weight: bold;">●</span> {' '.join([w['original'] for w in analyzed_words])}</div>
                    <div style="margin-bottom: 8px;"><span style="color: #2563eb; font-weight: bold;">●</span> {' '.join([w['morph'] for w in analyzed_words])}</div>
                    <div style="margin-bottom: 8px;"><span style="color: #059669; font-weight: bold;">●</span> {' '.join([w['gloss'] for w in analyzed_words])}</div>
                    <div style="margin-top: 12px; font-weight: bold; border-top: 1px solid #e5e7eb; padding-top: 8px;"><span style="color: #d97706;">●</span> {translation_text}</div>
                </div>
                """
                st.markdown(html_output, unsafe_allow_html=True)

                # 收集 CSV
                all_csv_data.append([f"Sentence {idx+1} - Line 1", ' '.join([w['original'] for w in analyzed_words])])
                all_csv_data.append([f"Sentence {idx+1} - Line 2", ' '.join([w['morph'] for w in analyzed_words])])
                all_csv_data.append([f"Sentence {idx+1} - Line 3", ' '.join([w['gloss'] for w in analyzed_words])])
                all_csv_data.append([f"Sentence {idx+1} - Line 4", translation_text])
                all_csv_data.append(["---", "---"])

        # 匯出分析結果
        csv = pd.DataFrame(all_csv_data).to_csv(index=False, header=False).encode('utf-8-sig')
        st.download_button("📥 匯出分析結果 (CSV)", csv, 'truku_analysis.csv', 'text/csv')

# ==========================================
# 側邊欄：新詞彙管理 (批次增加的秘密武器)
# ==========================================
if st.session_state["ai_generated_dict"]:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 AI 自動學習的新詞")
    st.sidebar.caption("這些是 AI 剛剛自動補充的單字，您可以下載後加回原始碼中。")
    
    # 轉成 DataFrame 顯示
    new_words_data = []
    for k, v in st.session_state["ai_generated_dict"].items():
        new_words_data.append({"單字": k, "構詞": v['morph'], "詞法": v['gloss'], "詞義": v['meaning']})
    
    df_new = pd.DataFrame(new_words_data)
    st.sidebar.dataframe(df_new, hide_index=True)
    
    # 提供下載新詞典格式
    # 格式化成 Python DICTIONARY 的字串格式，方便複製貼上
    dict_str = ""
    for k, v in st.session_state["ai_generated_dict"].items():
        dict_str += f'    "{k}": {{"morph": "{v["morph"]}", "gloss": "{v["gloss"]}", "meaning": "{v["meaning"]}"}},\n'
    
    st.sidebar.download_button(
        label="📥 下載新詞 (Python 格式)",
        data=dict_str,
        file_name="new_dictionary_entries.txt",
        mime="text/plain"
    )

st.markdown("---")
st.caption("資料來源參考：《太魯閣語語法概論》 + Gemini AI 自動補字 | 設計用途：族語教學與語料保存")
