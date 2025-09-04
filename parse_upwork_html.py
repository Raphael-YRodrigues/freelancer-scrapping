import csv, sys, re
from urllib.parse import urljoin
from selectolax.parser import HTMLParser

BASE = "https://www.upwork.com"

HIGHLIGHT_NOISE = re.compile(r"\bspan[-\s]?class[-\s]?highlight\b|</?span[^>]*>", re.I)
WS = re.compile(r"\s+")
MONEY = re.compile(r"([$\u20ac\u00a3])\s*([\d.,]+)(?:\s*[-–]\s*([$\u20ac\u00a3])?\s*([\d.,]+))?")

FRAMEWORK_DICT = [
    "Python","Scrapy","Selenium","BeautifulSoup","Requests","Pandas","NumPy",
    "Power BI","Tableau","Google Maps API","LinkedIn","GitHub","JavaScript","Node.js",
    "Playwright","Excel","Regex","API","ETL","Airflow"
]

def clean_text(s: str) -> str:
    if not s: return ""
    s = HIGHLIGHT_NOISE.sub(" ", s)
    s = WS.sub(" ", s).strip()
    return s

def canonical_url(u: str) -> str:
    if not u: return ""
    u = u.split("?", 1)[0]
    return u

def currency_code(sym: str) -> str:
    return {"$":"USD", "€":"EUR", "£":"GBP"}.get(sym, "")

def parse_price(article):
    # try fixed first
    price_type = ""
    price_min = price_max = ""
    currency = ""

    label = article.css_first("li[data-test='job-type-label'] strong")
    if label:
        t = label.text(strip=True).lower()
        if "hour" in t: price_type = "hourly"
        if "fixed" in t or "budget" in t: price_type = "fixed"

    # find numeric range in any price li
    li = article.css_first("li[data-test='is-fixed-price'], li[data-test='is-hourly']")
    txt = li.text(separator=" ", strip=True) if li else article.text(separator=" ", strip=True)
    m = MONEY.search(txt)
    if m:
        sym1, a1, sym2, a2 = m.groups()
        currency = currency_code(sym1 or sym2 or "")
        def norm(x): return float(x.replace(",",""))
        if a1 and a2:
            price_min, price_max = str(norm(a1)), str(norm(a2))
        elif a1:
            price_min = price_max = str(norm(a1))

    return price_type, currency, price_min, price_max

def infer_role(title, desc, skills_list):
    t = f"{title} {desc}".lower()
    s = " ".join(skills_list).lower()
    if "power bi" in t or "power bi" in s: return "Power BI Developer"
    if "data analyst" in t or "data analysis" in t: return "Data Analyst"
    if "web scraping" in t or "scraping" in t: return "Web Scraping Specialist"
    if "python" in t or "python" in s: return "Python Developer"
    if "etl" in t or "etl" in s: return "ETL Engineer"
    return ""

def extract_frameworks(text_blob, skills_list):
    blob = f"{text_blob} {' '.join(skills_list)}".lower()
    found = []
    for fw in FRAMEWORK_DICT:
        if fw.lower() in blob:
            found.append(fw)
    # de-dup but keep order
    seen, result = set(), []
    for x in found:
        if x not in seen:
            result.append(x); seen.add(x)
    return ", ".join(result)

def parse_article(a):
    # title + url
    a_title = a.css_first("a[data-test='job-tile-title-link']")
    title = clean_text(a_title.text(strip=True) if a_title else "")
    url = canonical_url(urljoin(BASE, a_title.attributes.get("href",""))) if a_title else ""

    # snippet
    p = a.css_first("p.text-body-sm") or a.css_first(".air3-line-clamp p, .air3-line-clamp")
    desc = clean_text(p.text(separator=" ", strip=True) if p else "")

    # skills/tags
    skills = [clean_text(s.text(strip=True)) for s in a.css("div.air3-token-container button.air3-token span") if clean_text(s.text(strip=True))]

    # price parsing
    price_type, currency, price_min, price_max = parse_price(a)

    role = infer_role(title, desc, skills)
    frameworks = extract_frameworks(f"{title} {desc}", skills)

    return {
        "platform": "upwork",
        "title": title,
        "description": desc,
        "role": role,
        "level": (a.css_first("li[data-test='experience-level'] strong").text(strip=True) if a.css_first("li[data-test='experience-level'] strong") else ""),
        "skills": ", ".join(skills),
        "frameworks": frameworks,
        "price_type": price_type,
        "currency": currency,
        "price_min": price_min,
        "price_max": price_max,
        "url": url,
    }

def main(in_path, out_csv="upwork_clean.csv"):
    html = open(in_path, "r", encoding="utf-8").read()
    dom = HTMLParser(html)
    arts = dom.css("article.job-tile")
    rows = [parse_article(a) for a in arts]

    fieldnames = ["platform","title","description","role","level","skills","frameworks",
                  "price_type","currency","price_min","price_max","url"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {out_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_upwork_html.py path/to/test.html [out.csv]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "upwork_clean.csv")
