import flet as ft
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
import random
import os  # 🌟 新增這行，讓程式能讀取系統環境
import flet as ft
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
import random

# --- 資料抓取 ---
def fetch_pilio_bingo():
    url = "https://www.pilio.idv.tw/bingo/list.asp"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding 
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.find_all('tr')
            bingo_data = []
            for row in rows:
                text = row.get_text(" ", strip=True)
                period_match = re.search(r'\b(11[3-5]\d{6})\b', text)
                if period_match:
                    period = period_match.group(1)
                    nums = re.findall(r'\b\d{2}\b', text)
                    valid_nums = [int(n) for n in nums if 1 <= int(n) <= 80 and n != period[:2]]
                    unique_nums = list(dict.fromkeys(valid_nums))
                    if len(unique_nums) >= 20:
                        bingo_data.append({"period": period, "numbers": unique_nums[:20]})
            return bingo_data
    except Exception as e: print(f"抓取錯誤: {e}")
    return []

# --- 核心策略池生成器 (提取 N1~N8 的號碼庫) ---
def get_strategy_pools(draws):
    if len(draws) < 10: return {}
    recent_2 = set(draws[0] + draws[1])
    counts_10 = Counter(num for draw in draws[:10] for num in draw)
    counts_5 = Counter(num for draw in draws[:5] for num in draw)

    pools = {}
    # N1 溫熱: 近10期 2~3次
    pools["N1_溫熱"] = [n for n, c in counts_10.items() if 2 <= c <= 3]
    # N2 回歸: 近10期 2次，近2期未開
    pools["N2_回歸"] = [n for n, c in counts_10.items() if c == 2 and n not in recent_2]
    # N3 拖號: 歷史同位拖曳
    n3_counts = Counter()
    latest_set = set(draws[0])
    for i in range(1, len(draws)):
        weight = len(set(draws[i]) & latest_set)
        if weight > 0:
            for num in draws[i-1]: n3_counts[num] += weight
    pools["N3_拖號"] = [n for n, c in n3_counts.most_common()]
    # N5 破冰: 遺漏最久
    missing = {num: len(draws) for num in range(1, 81)}
    for num in range(1, 81):
        for i, draw in enumerate(draws):
            if num in draw:
                missing[num] = i
                break
    pools["N5_破冰"] = sorted(missing.keys(), key=lambda x: missing[x], reverse=True)
    # N6 未開小號
    pools["N6_未開小號"] = [n for n in range(1, 11) if n not in recent_2]
    # N7 5熱
    pools["N7_5熱"] = [n for n, c in counts_5.most_common()]
    # N8 強尾
    tails_5 = Counter(num % 10 for draw in draws[:5] for num in draw)
    strong_tails = [t for t, c in tails_5.most_common()]
    pools["N8_強尾"] = [n for n, c in counts_5.items() if n % 10 in strong_tails]

    # 確保每個池子都有號碼防呆
    for k in pools:
        if not pools[k]: pools[k] = list(range(1, 81))
    return pools

# --- 🧠 動態權重評估大腦 (回測最近 5 期打分數) ---
def evaluate_strategies(data):
    # 初始化分數板
    scores = {k: 0 for k in ["N1_溫熱", "N2_回歸", "N3_拖號", "N5_破冰", "N6_未開小號", "N7_5熱", "N8_強尾"]}
    draws = [item["numbers"] for item in data]
    
    # 偷偷回到過去 5 期進行「模擬考」
    test_range = min(5, len(draws) - 10) 
    for i in range(test_range):
        past_draws = draws[i+1:] # 模擬當時能看到的歷史資料
        actual_result = set(draws[i]) # 當時實際開出的結果
        
        pools = get_strategy_pools(past_draws)
        for strat_name, pool in pools.items():
            # 取該策略當時最推薦的前 3 顆號碼來對答案
            top_picks = set(pool[:3])
            hits = len(top_picks & actual_result)
            scores[strat_name] += hits # 命中幾顆就加幾分
            
    # 將分數排序，變成動態權重排行榜
    ranked_strategies = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked_strategies

# --- 根據動態權重生成多星配號 ---
def generate_dynamic_stars(data, ranked_strats):
    draws = [item["numbers"] for item in data]
    current_pools = get_strategy_pools(draws)
    
    # 取出目前表現最好（權重最高）的前 3 個策略名稱
    top_1_strat = ranked_strats[0][0]
    top_2_strat = ranked_strats[1][0]
    top_3_strat = ranked_strats[2][0]

    results = {}
    
    def pick_dynamic(count, picked_set):
        selected = []
        # 依照權重順序，優先從最強的策略池挑號碼
        for strat in [top_1_strat, top_2_strat, top_3_strat]:
            pool = current_pools[strat]
            for num in pool:
                if num not in picked_set and num not in selected:
                    selected.append(num)
                if len(selected) >= count:
                    picked_set.update(selected)
                    return selected
        return selected

    # 動態配號：不再用死板公式，完全信任當下最強的 AI 策略
    for stars in range(2, 11):
        picked = set()
        star_nums = pick_dynamic(stars, picked)
        results[f"{stars} 星"] = sorted(star_nums)
        
    return results

# --- UI 繪圖工具 ---
def create_ball(number, color="blue900"):
    return ft.Container(
        content=ft.Text(f"{number:02d}", size=14, weight="bold", color="white"),
        width=30, height=30, bgcolor=color, border_radius=15, alignment=ft.alignment.center
    )

# --- Flet 主介面邏輯 ---
def main(page: ft.Page):
    page.title = "賓果 AI 動態權重大腦"
    page.theme_mode = "dark" 
    page.padding = 20
    page.scroll = "auto" 

    app_data = {"raw_data": []}

    title = ft.Text("🧠 賓果 AI 動態權重預測", size=26, weight="bold", color="amber")
    status_text = ft.Text("狀態：等待抓取...", color="grey")

    latest_draws_section = ft.Column(spacing=10)
    ai_dashboard_section = ft.Column(spacing=10) # 顯示 AI 戰力表的區塊
    prediction_section = ft.Column(spacing=15)

    def on_click_predict(e):
        if not app_data["raw_data"]: return
        status_text.value = "🧠 AI 正在進行歷史回測與權重運算..."
        page.update()

        # 1. 執行回測，取得各策略戰力分數
        ranked_strats = evaluate_strategies(app_data["raw_data"])
        
        # 2. 顯示 AI 戰力儀表板
        ai_dashboard_section.controls.clear()
        ai_dashboard_section.controls.append(ft.Text("📊 AI 策略近期戰力評估 (動態權重)：", weight="bold", color="cyan"))
        
        for strat, score in ranked_strats:
            # 依據分數顯示不同的熱度圖標
            icon = "🔥" if score >= 3 else ("👍" if score > 0 else "🧊")
            ai_dashboard_section.controls.append(
                ft.Text(f"{icon} {strat.replace('_', ' ')} : 戰力積分 {score}", color="white70")
            )

        # 3. 根據最強權重進行多星預測
        preds = generate_dynamic_stars(app_data["raw_data"], ranked_strats)
        
        prediction_section.controls.clear()
        prediction_section.controls.append(
            ft.Text("🎯 根據當前最強策略，AI 動態推薦組合：", size=20, weight="bold", color="green400")
        )

        for star, nums in preds.items():
            balls_row = ft.Row([create_ball(n, color="red800") for n in nums], wrap=True)
            prediction_section.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{star} 組合", weight="bold", color="amber300", size=16),
                        balls_row
                    ]),
                    bgcolor="grey900", padding=10, border_radius=8
                )
            )
            
        status_text.value = "✅ AI 動態權重預測完成！"
        page.update()

    def on_click_fetch(e):
        status_text.value = "⏳ 正在連線抓取資料中..."
        status_text.color = "yellow"
        fetch_btn.disabled = predict_btn.disabled = True 
        page.update()

        data = fetch_pilio_bingo()
        if data:
            app_data["raw_data"] = data
            status_text.value = f"✅ 成功抓取！總共 {len(data)} 期資料。"
            status_text.color = "green"
            
            latest_draws_section.controls.clear() 
            if len(data) >= 2:
                latest_draws_section.controls.append(
                    ft.Text("⚠️ 最新獎號確認：", size=16, color="red300", weight="bold")
                )
                for i in range(2):
                    period = data[i]["period"]
                    balls = ft.Row([create_ball(n) for n in data[i]["numbers"]], wrap=True, spacing=5)
                    latest_draws_section.controls.append(
                        ft.Column([ft.Text(f"第 {period} 期：", size=18, weight="bold", color="cyan"), balls, ft.Divider(height=5, color="transparent")])
                    )
            predict_btn.disabled = False
            ai_dashboard_section.controls.clear()
            prediction_section.controls.clear()
        else:
            status_text.value = "⚠️ 沒抓到資料，請檢查網路。"
            status_text.color = "red"
        
        fetch_btn.disabled = False
        page.update()

    fetch_btn = ft.ElevatedButton("🚀 1. 抓取 / 更新最新獎號", on_click=on_click_fetch, bgcolor="blue700", color="white")
    predict_btn = ft.ElevatedButton("🧠 2. 啟動 AI 動態大腦", on_click=on_click_predict, bgcolor="purple700", color="white", disabled=True)

    page.add(
        title, ft.Row([fetch_btn, predict_btn], wrap=True), status_text, 
        ft.Divider(), latest_draws_section, 
        ft.Divider(), ai_dashboard_section, # 顯示戰力表的區塊
        ft.Divider(), prediction_section
    )

# 🌟 自動抓取雲端主機給的 Port，如果在自己電腦跑就預設用 8550
port = int(os.environ.get("PORT", 8550))

import flet as ft
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
import random
import os  # 🌟 新增這行，讓程式能讀取系統環境
import flet as ft
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
import random

# --- 資料抓取 ---
def fetch_pilio_bingo():
    url = "https://www.pilio.idv.tw/bingo/list.asp"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding 
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.find_all('tr')
            bingo_data = []
            for row in rows:
                text = row.get_text(" ", strip=True)
                period_match = re.search(r'\b(11[3-5]\d{6})\b', text)
                if period_match:
                    period = period_match.group(1)
                    nums = re.findall(r'\b\d{2}\b', text)
                    valid_nums = [int(n) for n in nums if 1 <= int(n) <= 80 and n != period[:2]]
                    unique_nums = list(dict.fromkeys(valid_nums))
                    if len(unique_nums) >= 20:
                        bingo_data.append({"period": period, "numbers": unique_nums[:20]})
            return bingo_data
    except Exception as e: print(f"抓取錯誤: {e}")
    return []

# --- 核心策略池生成器 (提取 N1~N8 的號碼庫) ---
def get_strategy_pools(draws):
    if len(draws) < 10: return {}
    recent_2 = set(draws[0] + draws[1])
    counts_10 = Counter(num for draw in draws[:10] for num in draw)
    counts_5 = Counter(num for draw in draws[:5] for num in draw)

    pools = {}
    # N1 溫熱: 近10期 2~3次
    pools["N1_溫熱"] = [n for n, c in counts_10.items() if 2 <= c <= 3]
    # N2 回歸: 近10期 2次，近2期未開
    pools["N2_回歸"] = [n for n, c in counts_10.items() if c == 2 and n not in recent_2]
    # N3 拖號: 歷史同位拖曳
    n3_counts = Counter()
    latest_set = set(draws[0])
    for i in range(1, len(draws)):
        weight = len(set(draws[i]) & latest_set)
        if weight > 0:
            for num in draws[i-1]: n3_counts[num] += weight
    pools["N3_拖號"] = [n for n, c in n3_counts.most_common()]
    # N5 破冰: 遺漏最久
    missing = {num: len(draws) for num in range(1, 81)}
    for num in range(1, 81):
        for i, draw in enumerate(draws):
            if num in draw:
                missing[num] = i
                break
    pools["N5_破冰"] = sorted(missing.keys(), key=lambda x: missing[x], reverse=True)
    # N6 未開小號
    pools["N6_未開小號"] = [n for n in range(1, 11) if n not in recent_2]
    # N7 5熱
    pools["N7_5熱"] = [n for n, c in counts_5.most_common()]
    # N8 強尾
    tails_5 = Counter(num % 10 for draw in draws[:5] for num in draw)
    strong_tails = [t for t, c in tails_5.most_common()]
    pools["N8_強尾"] = [n for n, c in counts_5.items() if n % 10 in strong_tails]

    # 確保每個池子都有號碼防呆
    for k in pools:
        if not pools[k]: pools[k] = list(range(1, 81))
    return pools

# --- 🧠 動態權重評估大腦 (回測最近 5 期打分數) ---
def evaluate_strategies(data):
    # 初始化分數板
    scores = {k: 0 for k in ["N1_溫熱", "N2_回歸", "N3_拖號", "N5_破冰", "N6_未開小號", "N7_5熱", "N8_強尾"]}
    draws = [item["numbers"] for item in data]
    
    # 偷偷回到過去 5 期進行「模擬考」
    test_range = min(5, len(draws) - 10) 
    for i in range(test_range):
        past_draws = draws[i+1:] # 模擬當時能看到的歷史資料
        actual_result = set(draws[i]) # 當時實際開出的結果
        
        pools = get_strategy_pools(past_draws)
        for strat_name, pool in pools.items():
            # 取該策略當時最推薦的前 3 顆號碼來對答案
            top_picks = set(pool[:3])
            hits = len(top_picks & actual_result)
            scores[strat_name] += hits # 命中幾顆就加幾分
            
    # 將分數排序，變成動態權重排行榜
    ranked_strategies = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked_strategies

# --- 根據動態權重生成多星配號 ---
def generate_dynamic_stars(data, ranked_strats):
    draws = [item["numbers"] for item in data]
    current_pools = get_strategy_pools(draws)
    
    # 取出目前表現最好（權重最高）的前 3 個策略名稱
    top_1_strat = ranked_strats[0][0]
    top_2_strat = ranked_strats[1][0]
    top_3_strat = ranked_strats[2][0]

    results = {}
    
    def pick_dynamic(count, picked_set):
        selected = []
        # 依照權重順序，優先從最強的策略池挑號碼
        for strat in [top_1_strat, top_2_strat, top_3_strat]:
            pool = current_pools[strat]
            for num in pool:
                if num not in picked_set and num not in selected:
                    selected.append(num)
                if len(selected) >= count:
                    picked_set.update(selected)
                    return selected
        return selected

    # 動態配號：不再用死板公式，完全信任當下最強的 AI 策略
    for stars in range(2, 11):
        picked = set()
        star_nums = pick_dynamic(stars, picked)
        results[f"{stars} 星"] = sorted(star_nums)
        
    return results

# --- UI 繪圖工具 ---
def create_ball(number, color="blue900"):
    return ft.Container(
        content=ft.Text(f"{number:02d}", size=14, weight="bold", color="white"),
        width=30, height=30, bgcolor=color, border_radius=15, alignment=ft.alignment.center
    )

# --- Flet 主介面邏輯 ---
def main(page: ft.Page):
    page.title = "賓果 AI 動態權重大腦"
    page.theme_mode = "dark" 
    page.padding = 20
    page.scroll = "auto" 

    app_data = {"raw_data": []}

    title = ft.Text("🧠 賓果 AI 動態權重預測", size=26, weight="bold", color="amber")
    status_text = ft.Text("狀態：等待抓取...", color="grey")

    latest_draws_section = ft.Column(spacing=10)
    ai_dashboard_section = ft.Column(spacing=10) # 顯示 AI 戰力表的區塊
    prediction_section = ft.Column(spacing=15)

    def on_click_predict(e):
        if not app_data["raw_data"]: return
        status_text.value = "🧠 AI 正在進行歷史回測與權重運算..."
        page.update()

        # 1. 執行回測，取得各策略戰力分數
        ranked_strats = evaluate_strategies(app_data["raw_data"])
        
        # 2. 顯示 AI 戰力儀表板
        ai_dashboard_section.controls.clear()
        ai_dashboard_section.controls.append(ft.Text("📊 AI 策略近期戰力評估 (動態權重)：", weight="bold", color="cyan"))
        
        for strat, score in ranked_strats:
            # 依據分數顯示不同的熱度圖標
            icon = "🔥" if score >= 3 else ("👍" if score > 0 else "🧊")
            ai_dashboard_section.controls.append(
                ft.Text(f"{icon} {strat.replace('_', ' ')} : 戰力積分 {score}", color="white70")
            )

        # 3. 根據最強權重進行多星預測
        preds = generate_dynamic_stars(app_data["raw_data"], ranked_strats)
        
        prediction_section.controls.clear()
        prediction_section.controls.append(
            ft.Text("🎯 根據當前最強策略，AI 動態推薦組合：", size=20, weight="bold", color="green400")
        )

        for star, nums in preds.items():
            balls_row = ft.Row([create_ball(n, color="red800") for n in nums], wrap=True)
            prediction_section.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{star} 組合", weight="bold", color="amber300", size=16),
                        balls_row
                    ]),
                    bgcolor="grey900", padding=10, border_radius=8
                )
            )
            
        status_text.value = "✅ AI 動態權重預測完成！"
        page.update()

    def on_click_fetch(e):
        status_text.value = "⏳ 正在連線抓取資料中..."
        status_text.color = "yellow"
        fetch_btn.disabled = predict_btn.disabled = True 
        page.update()

        data = fetch_pilio_bingo()
        if data:
            app_data["raw_data"] = data
            status_text.value = f"✅ 成功抓取！總共 {len(data)} 期資料。"
            status_text.color = "green"
            
            latest_draws_section.controls.clear() 
            if len(data) >= 2:
                latest_draws_section.controls.append(
                    ft.Text("⚠️ 最新獎號確認：", size=16, color="red300", weight="bold")
                )
                for i in range(2):
                    period = data[i]["period"]
                    balls = ft.Row([create_ball(n) for n in data[i]["numbers"]], wrap=True, spacing=5)
                    latest_draws_section.controls.append(
                        ft.Column([ft.Text(f"第 {period} 期：", size=18, weight="bold", color="cyan"), balls, ft.Divider(height=5, color="transparent")])
                    )
            predict_btn.disabled = False
            ai_dashboard_section.controls.clear()
            prediction_section.controls.clear()
        else:
            status_text.value = "⚠️ 沒抓到資料，請檢查網路。"
            status_text.color = "red"
        
        fetch_btn.disabled = False
        page.update()

    fetch_btn = ft.ElevatedButton("🚀 1. 抓取 / 更新最新獎號", on_click=on_click_fetch, bgcolor="blue700", color="white")
    predict_btn = ft.ElevatedButton("🧠 2. 啟動 AI 動態大腦", on_click=on_click_predict, bgcolor="purple700", color="white", disabled=True)

    page.add(
        title, ft.Row([fetch_btn, predict_btn], wrap=True), status_text, 
        ft.Divider(), latest_draws_section, 
        ft.Divider(), ai_dashboard_section, # 顯示戰力表的區塊
        ft.Divider(), prediction_section
    )

# 🌟 自動抓取雲端主機給的 Port，如果在自己電腦跑就預設用 8550
port = int(os.environ.get("PORT", 8550))
# 加上 AppView. 讓新舊版 Flet 都能看得懂
ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
