# -*- coding: utf-8 -*-
"""详细推送：地区 + 业务名称"""
import json, os, sys, time, hmac, base64, hashlib, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

WEBHOOK = os.getenv("WECOM_WEBHOOK", "").strip()
SINCE_HOURS = float(os.getenv("SINCE_HOURS") or "24")
SITE_ROOT = "."
FOCUS_LIST = ["hunan", "guangdong", "guizhou"]
SITE_URL = "https://woshiyigemanhuajia.github.io/hunan-tariff-site/"

SITES = [
    ("data/history.json", "移动", "🔵"),
    ("unicom/data/history.json", "联通", "🟠"),
    ("telecom/data/history.json", "电信", "🟢"),
    ("gb/data/history.json", "广电", "🟣"),
]

SEC_CN = {
    "quanguo": "全网", "hunan": "湖南", "guangdong": "广东", "guizhou": "贵州",
    "beijing": "北京", "shanghai": "上海", "zhejiang": "浙江", "jiangsu": "江苏",
}

def sec_cn(k):
    return SEC_CN.get(str(k).strip().lower(), k)

def parse_ts(ts):
    if not ts: return None
    s = str(ts).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try: return datetime.strptime(s, fmt).replace(tzinfo=timezone(timedelta(hours=8)))
        except: continue
    return None

def load_json(path):
    fp = os.path.join(SITE_ROOT, path)
    if not os.path.exists(fp): return []
    try:
        with open(fp, encoding="utf-8") as f: return json.load(f)
    except: return []

def main():
    now = datetime.now(timezone(timedelta(hours=8)))
    since = now - timedelta(hours=SINCE_HOURS)
    
    lines = ["## 📊 资费变化详细汇总", "",
             f"**时间**：{since.strftime('%m-%d %H:%M')} ~ {now.strftime('%m-%d %H:%M')}", ""]
    
    grand = [0, 0, 0]
    
    for path, name, icon in SITES:
        hist = load_json(path)
        a, r, m = 0, 0, 0
        secs = []
        
        for e in hist:
            dt = parse_ts(e.get("ts"))
            if dt and dt >= since:
                for k, v in e.items():
                    if k == "ts" or not isinstance(v, dict): continue
                    aa = int(v.get("added", 0) or 0)
                    rr = int(v.get("removed", 0) or 0)
                    mm = int(v.get("modified", 0) or 0)
                    if aa or rr or mm:
                        a += aa; r += rr; m += mm
                        secs.append((sec_cn(k), aa, rr, mm))
        
        grand[0] += a; grand[1] += r; grand[2] += m
        
        if not (a or r or m):
            lines.append(f"- {icon} **{name}**：无变化")
            continue
        
        lines.append(f"- {icon} **{name}**：新增 {a}、下架 {r}、修改 {m}")
        
        for sec_name, aa, rr, mm in secs[:5]:
            if aa or rr or mm:
                lines.append(f"  └ 📍 {sec_name}：+{aa} -{rr} ~{mm}")
    
    lines.append("")
    lines.append(f"**合计**：新增 {grand[0]}、下架 {grand[1]}、修改 {grand[2]}")
    lines.append("")
    lines.append(f"🔗 [查看详情]({SITE_URL}/)")
    
    text = "\n".join(lines)
    print(text)
    
    if WEBHOOK:
        try:
            req = urllib.request.Request(
                WEBHOOK,
                data=json.dumps({"msgtype": "markdown", "markdown": {"content": text[:3800]}}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            res = json.load(urllib.request.urlopen(req, timeout=30))
            print(f"推送：{'✅' if res.get('errcode')==0 else '❌'} {res.get('errmsg')}")
        except Exception as e:
            print(f"推送失败：{e}")
    else:
        print("未配置 WECOM_WEBHOOK")

if __name__ == "__main__":
    main()
