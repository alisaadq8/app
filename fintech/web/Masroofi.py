# -*- coding: utf-8 -*-
# MasroofiGPT — Single-file Streamlit App (Improved Navigation & UX)
# ================================================================
# صفحات:
#   1) Home: إدخال/تعديل البيانات + انتقال ذكي
#   2) MasroofiGPT: شات + أنشطة يمين + نقاط/شارات + اقتراح تقرير
#   3) Parent Dashboard: تقرير رسمي من OpenAI + Checklist + PDF + رجوع/تعديل
#
# مفاتيح:
#   - يأخذ OPENAI_API_KEY من متغيرات البيئة فقط (لا secrets.toml)
#   - أوتو-سكرول، مؤشر "يكتب…"، منع سبام، إعادة محاولة للـAPI، RTL، بطاقات جميلة
#
# تشغيل:
#   pip install streamlit openai reportlab streamlit-option-menu
#   streamlit run Masroofi.py

import os, json, time, io, random, textwrap, datetime
from pathlib import Path

import streamlit as st
from streamlit_option_menu import option_menu

# -------- OpenAI client ----------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

API_KEY = os.getenv("OPENAI_API_KEY", "") or os.getenv("OPENAI_APIKEY", "")
client = None
if API_KEY and OpenAI:
    try:
        client = OpenAI(api_key=API_KEY)
    except Exception:
        client = None

# -------- PDF ----------
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

# -------- Page config & CSS ----------
st.set_page_config(page_title="MasroofiGPT", page_icon="💳", layout="wide")

CSS = """
<style>
/* RTL أساس */
.block-container { direction: rtl; }
html, body, [class*="css"] { font-family: "Segoe UI", system-ui, -apple-system, sans-serif; }
h1,h2,h3 { letter-spacing: .2px }

/* ترويسة مثبتة خفيفة */
.topbar {
  position: sticky; top: 0; z-index: 10;
  background: #ffffffcc; backdrop-filter: blur(6px);
  border-bottom: 1px solid #eee; padding: 6px 0 8px 0; margin-bottom: 8px;
}

/* بطاقات */
.card { background:#fff; border:1px solid #eee; border-radius:12px; padding:14px; }
.card + .card { margin-top:12px; }

/* شات */
.chat-wrap { background:#fff; border:1px solid #eee; border-radius:14px; min-height:380px; padding:12px; }
.mas-bubble-user {
  background:#E6F7EC; border:1px solid #cfead8; color:#123;
  padding:12px 14px; border-radius:14px; margin:10px 0; width: fit-content; margin-left:auto;
  font-size:17px; line-height:1.7;
}
.mas-bubble-bot {
  background:#F4F7FF; border:1px solid #dfE6ff; color:#123;
  padding:12px 14px; border-radius:14px; margin:10px 0; width: fit-content;
  font-size:17px; line-height:1.8;
}

/* اقتراحات تحت الشات */
.pills { margin-top:6px; display:flex; flex-wrap:wrap; gap:8px; }
.pill {
  background:#46a36a; color:#fff; border-radius:999px; padding:8px 12px; font-size:15px; cursor:pointer;
}
.pill:hover { filter:brightness(.92); }

/* شريط اقتراح تقرير */
.banner {
  border:1px solid #f2c; border-radius:12px; background:#fff0f6;
  padding:10px 12px; margin:8px 0;
}

/* أسفل الشات */
.stChatFloatingInputContainer { max-width: 900px; margin:0 auto; }

/* أوتو سكرول */
#anchor { height:1px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------- State ----------
def init_state():
    ss = st.session_state
    ss.setdefault("nav", 0)  # 0 Home, 1 GPT, 2 Parent
    # بيانات
    ss.setdefault("child_name", "")
    ss.setdefault("age", 10)
    ss.setdefault("allowance", 0.0)
    ss.setdefault("cycle", "Weekly")           # Weekly / Monthly
    ss.setdefault("goal_choice", "Saving money")  # Saving money / Buy a game
    # شات
    ss.setdefault("chat", [])
    ss.setdefault("cool_ts", 0.0)
    ss.setdefault("typing", False)
    ss.setdefault("pending", None)
    ss.setdefault("run_id", "")
    # أنشطة
    ss.setdefault("points", 0)
    ss.setdefault("badges", [])
    ss.setdefault("level", 1)
    ss.setdefault("riddles_results", [])
    ss.setdefault("game_results", [])
    ss.setdefault("mcq_riddle", None)
    ss.setdefault("mcq_save", None)
    # تقرير ولي الأمر
    ss.setdefault("parent_prompted", False)
    ss.setdefault("parent_report", "")
    ss.setdefault("parent_notes", "")
    # خيارات
    ss.setdefault("show_mini_chat_in_parent", False)
init_state()

# -------- Helpers ----------
def award():
    pts = int(st.session_state.points)
    badges = set(st.session_state.badges)
    lvl = 1
    if pts >= 5: badges.add("Starter ⭐"); lvl = 2
    if pts >= 15: badges.add("Smart Saver 🥈"); lvl = 3
    if pts >= 30: badges.add("Finance Hero 🥇"); lvl = 4
    st.session_state.badges = sorted(list(badges))
    st.session_state.level = lvl

def safe_ai(system, user, temp=0.6, retries=3, model="gpt-4o-mini"):
    if not client:
        return "الذكاء الاصطناعي غير متاح الآن، جرب لاحقًا. تلميح: استخدم قاعدة 50/30/20 مع هدف أسبوعي بسيط."
    err = None
    for i in range(retries):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":system},{"role":"user","content":user}],
                temperature=temp
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            err = e; time.sleep(0.7*(i+1))
    return "حاولنا أكثر من مرة وما زال فيه مشكلة بالاتصال. خلنا نجرب بعد شوي 🙏"

def ask_masroofi(txt):
    age = int(st.session_state.get("age", 10))
    name = st.session_state.get("child_name") or "صديقي"
    mood = "ودود جدًا وبسيط" if age<=8 else "لطيف وواضح" if age<=12 else "قريب من لغة المراهقين ومشجع"
    sys = ("أنت مصروفي، مساعد مالي تربوي، عربي، لطيف، يصحّح بخطاب تربوي ويحمي الطفل من السلوكيات غير المناسبة."
           " اجعل الرد قصيرًا ومقسمًا لنقاط عند الحاجة، وبأمثلة واقعية مناسبة للعمر.")
    usr = f"العمر: {age}\nالاسم: {name}\nالهدف: {st.session_state.goal_choice}\nالمصروف {st.session_state.cycle}: {st.session_state.allowance}\nأسلوب: {mood}\n\nسؤال الطفل: {txt}"
    return safe_ai(sys, usr, temp=0.6)

def fallback_mcq(kind, age=10):
    if kind=="riddle":
        return {"title":"Riddle","question":"معي 10 عملات، ادخرت 2 اليوم—كم بقي؟","options":["6","8","10"],"answer_index":1,"explain":"10 - 2 = 8"}
    return {"title":"Saving","question":"أبي لعبة سعرها 12 وعندي 10—الأفضل؟","options":["أستلف","أنتظر وأدخر","أشتري الأرخص فورًا"],"answer_index":1,"explain":"الانتظار والادخار قرار صحي"}

def make_mcq(kind):
    age = int(st.session_state.get("age",10))
    if not client: return fallback_mcq(kind, age)
    sys = "منشئ أسئلة اختيار من متعدد للأطفال. أعد JSON فقط بالمفاتيح: title, question, options(3), answer_index, explain."
    usr = f"أنشئ {'لغزًا ماليًا' if kind=='riddle' else 'سؤال ادخار'} مناسبًا لعمر {age}. JSON فقط بلا أي شرح خارج JSON."
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys},{"role":"user","content":usr}],
            temperature=0.4
        )
        data = json.loads((r.choices[0].message.content or "").strip())
        if not isinstance(data.get("options"), list) or len(data["options"]) != 3:
            raise ValueError("bad options")
        return data
    except Exception:
        return fallback_mcq(kind, age)

def make_parent_report():
    msgs = []
    for role,content in st.session_state.chat[-15:]:
        who = "طفل" if role=="user" else "مصروفي"
        msgs.append(f"{who}: {content[:220]}")
    summary = "\n".join(msgs) if msgs else "لا توجد مقتطفات."
    notes = st.session_state.parent_notes.strip() or "لا توجد."
    child = st.session_state.child_name or "طفلك"
    age   = int(st.session_state.age)
    pts   = int(st.session_state.points)
    badges= ", ".join(st.session_state.badges) or "لا يوجد"
    prompt = f"""
أنت مستشار تربوي مالي. اكتب تقريرًا رسميًا لوليّ الأمر عن "{child}" (العمر: {age}).
ملاحظات وليّ الأمر: {notes}
المعطيات: نقاط={pts}، شارات={badges}
مقتطفات حديثة:
{summary}

المطلوب (مختصر مهني 250-350 كلمة):
- ملخص سلوكي مالي
- نقاط قوة
- فرص تحسين تربوية
- خطة أسبوعية (5 نقاط)
""".strip()
    if client:
        sys = "خبير تربية مالية للأسر، لغة مهنية محترمة."
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys},{"role":"user","content":prompt}],
            temperature=0.5
        )
        st.session_state.parent_report = (r.choices[0].message.content or "").strip()
    else:
        st.session_state.parent_report = "تقرير مبدئي: الاستمرار على أسئلة قصيرة وأهداف أسبوعية بسيطة…"

def checklist_table(cycle, title):
    if cycle=="Weekly":
        cols = ["الأسبوع 1","الأسبوع 2","الأسبوع 3","الأسبوع 4"]
        rows = ["التزم بالادخار","قارن الأسعار","سجّل مصروفك","ناقش قراراً"]
    else:
        cols = ["الشهر 1","الشهر 2","الشهر 3"]
        rows = ["ادخار شهري","تتبع","تحقيق هدف صغير","تقييم"]
    html = "<table style='width:100%;border-collapse:collapse' border='1'>"
    html += "<tr><th style='padding:6px'>المهمة</th>" + "".join([f"<th style='padding:6px'>{c}</th>" for c in cols]) + "</tr>"
    for r in rows:
        html += "<tr><td style='padding:6px'>" + r + "</td>" + "".join(["<td style='padding:10px'></td>" for _ in cols]) + "</tr>"
    html += "</table>"
    return html

def checklist_pdf(cycle, title):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W,H = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, H-2*cm, f"Masroofi Checklist - {title} ({cycle})")
    c.setFont("Helvetica", 11)
    if cycle=="Weekly":
        cols = ["الأسبوع 1","الأسبوع 2","الأسبوع 3","الأسبوع 4"]
        rows = ["التزم بالادخار","قارن الأسعار","سجّل مصروفك","ناقش قراراً"]
    else:
        cols = ["الشهر 1","الشهر 2","الشهر 3"]
        rows = ["ادخار شهري","تتبع","تحقيق هدف صغير","تقييم"]
    x0, y = 2*cm, H-3*cm
    c.drawString(x0, y, "المهمة")
    for i,col in enumerate(cols):
        c.drawString(x0+(i+1)*4*cm, y, col)
    y -= .7*cm
    for r in rows:
        c.drawString(x0, y, r)
        for i in range(len(cols)):
            c.rect(x0+(i+1)*4*cm, y-.1*cm, 0.5*cm, 0.5*cm)
        y -= .9*cm
    c.showPage(); c.save(); buf.seek(0)
    return buf.read()

# -------- Top navigation ----------
def top_nav():
    with st.container():
        st.markdown('<div class="topbar">', unsafe_allow_html=True)
        selected = option_menu(
            "",
            ["🏠 Home", "💬 MasroofiGPT", "👨‍👩‍👦 Parent"],
            icons=["house","chat-dots","people"],
            menu_icon="cast",
            default_index=st.session_state.nav,
            orientation="horizontal",
            styles={
                "container":{"padding":"0!important"},
                "nav-link":{"font-size":"16px","--hover-color":"#eee"},
                "nav-link-selected":{"background-color":"#e7505a","color":"#fff"}
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)
    mapping = {"🏠 Home":0,"💬 MasroofiGPT":1,"👨‍👩‍👦 Parent":2}
    idx = mapping.get(selected,0)
    if idx != st.session_state.nav:
        st.session_state.nav = idx
        st.rerun()

# -------- Sidebar quick actions ----------
with st.sidebar:
    st.header("⚡ تنقّل سريع")
    if st.button("⬅️ رجوع إلى MasroofiGPT"):
        st.session_state.nav = 1; st.rerun()
    if st.button("✏️ تعديل البيانات"):
        st.session_state.nav = 0; st.rerun()
    st.divider()
    st.caption("المفتاح من الجهاز فقط. لو ما وُجد، نستخدم ردود بديلة.")

# -------- Pages ----------
def page_home():
    st.title("MasroofiGPT 💳")
    st.subheader("البيانات الأساسية")
    name = st.text_input("الاسم (اختياري):", value=st.session_state.child_name, key="home_name")
    c1,c2 = st.columns(2)
    with c1:
        age = st.number_input("العمر:", min_value=4, max_value=16, value=int(st.session_state.age), step=1, key="home_age")
    with c2:
        allowance = st.number_input("المصروف (بالريال):", min_value=0.0, step=1.0, value=float(st.session_state.allowance), key="home_allow")
    c3,c4 = st.columns(2)
    with c3:
        cycle = st.radio("المتابعة:", ["Weekly","Monthly"], index=0 if st.session_state.cycle=="Weekly" else 1, horizontal=True, key="home_cycle")
    with c4:
        goal = st.radio("هدفك الحالي:", ["Saving money","Buy a game"], index=0 if st.session_state.goal_choice=="Saving money" else 1, horizontal=True, key="home_goal")
    st.toggle("تفعيل شات مصغّر داخل لوحة وليّ الأمر (اختياري)", key="show_mini_chat_in_parent")

    cols = st.columns([2,1,1])
    if cols[0].button("💾 حفظ والانتقال إلى MasroofiGPT", use_container_width=True):
        st.session_state.child_name = name.strip()
        st.session_state.age = int(age)
        st.session_state.allowance = float(allowance)
        st.session_state.cycle = cycle
        st.session_state.goal_choice = goal
        st.session_state.nav = 1
        st.success("تم الحفظ! نراك في صفحة مصروفي 😉")
        st.rerun()
    if cols[1].button("🧹 مسح المحادثة"):
        st.session_state.chat = []
        st.toast("تم مسح المحادثة.")
    if cols[2].button("🔄 إعادة تعيين النقاط"):
        st.session_state.points = 0
        st.session_state.badges = []
        st.session_state.level = 1
        st.toast("تمت إعادة تعيين النقاط والشارات.")

    st.caption("خصوصيتكم مهمة: لا نطلب نوع الطفل. التخصيص يتم تلقائيًا حسب العمر فقط.")

def page_gpt():
    st.subheader("MasroofiGPT (مساعد مالي تربوي)")
    # شريط اقتراح تقرير (بدل التحويل الإجباري)
    if st.session_state.parent_prompted:
        with st.container():
            c1, c2, c3 = st.columns([3,2,1])
            c1.markdown('<div class="banner">🎉 جاهزين نعرض تقرير وليّ الأمر المبني على المحادثة والأنشطة؟</div>', unsafe_allow_html=True)
            if c2.button("📄 اعرض التقرير الآن"):
                make_parent_report()
                st.session_state.nav = 2
                st.session_state.parent_prompted = False
                st.rerun()
            if c3.button("✋ لاحقًا"):
                st.session_state.parent_prompted = False
                st.toast("تمام، كمل دردشة مع مصروفي 🤝")

    col_chat, col_side = st.columns([3,1], vertical_alignment="top")

    with col_chat:
        st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
        for role, text in st.session_state.chat[-120:]:
            if role == "user":
                st.markdown(f'<div class="mas-bubble-user">{text}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="mas-bubble-bot">{text}</div>', unsafe_allow_html=True)

        # اقتراحات
        st.markdown('<div class="pills">', unsafe_allow_html=True)
        sugg = ["كيف أزيد مصروفي؟","أبي خطة ادخار ممتعة 🎮","فكرة ادخار سريعة 🎯","كيف أقارن الأسعار؟"]
        scols = st.columns(len(sugg))
        for i, s in enumerate(sugg):
            if scols[i].button(s, key=f"pill_{i}"):
                st.session_state.pending = s
        st.markdown('</div>', unsafe_allow_html=True)

        # مؤشر كتابة
        if st.session_state.typing:
            st.info("مصروفي يكتب…")

        # مرساة أوتو سكرول
        st.markdown('<div id="anchor"></div>', unsafe_allow_html=True)
        st.markdown('<script>document.getElementById("anchor").scrollIntoView();</script>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_side:
        # نقاط/شارات
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🏅 نقاطي")
        award()
        st.metric("النقاط", int(st.session_state.points))
        st.write("مستوى:", st.session_state.level)
        st.write("شارات:", " | ".join(st.session_state.badges) if st.session_state.badges else "—")
        st.markdown('</div>', unsafe_allow_html=True)

        # لغز ذكي
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🧩 لغز ذكي")
        if st.button("توليد لغز"):
            st.session_state.mcq_riddle = make_mcq("riddle")
            st.toast("تم توليد لغز!")
        r = st.session_state.mcq_riddle
        if r:
            st.write("**" + r["question"] + "**")
            b1,b2,b3 = st.columns(3)
            for i, lab in enumerate(r["options"]):
                if [b1,b2,b3][i].button(lab, key=f"r_{i}"):
                    ok = (i == r["answer_index"])
                    pts = 2 if ok else 0
                    st.session_state.points += pts
                    st.session_state.riddles_results.append({"q":r["question"],"choice":lab,"ok":ok,"pts":pts})
                    st.session_state.chat.append(("assistant", "نتيجة لغز: " + ("صحيح 🎉" if ok else "غير صحيح") + f" — {r['explain']}"))
                    # اقتراح عرض تقرير مرة واحدة
                    if len(st.session_state.riddles_results) >= 1 and len(st.session_state.chat) >= 4:
                        st.session_state.parent_prompted = True

        st.markdown('</div>', unsafe_allow_html=True)

        # لعبة ادخار
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("💰 لعبة ادخار")
        if st.button("توليد سؤال ادخار"):
            st.session_state.mcq_save = make_mcq("save")
            st.toast("تم توليد سؤال ادخار!")
        s = st.session_state.mcq_save
        if s:
            st.write("**" + s["question"] + "**")
            c1,c2,c3 = st.columns(3)
            for i, lab in enumerate(s["options"]):
                if [c1,c2,c3][i].button(lab, key=f"s_{i}"):
                    ok = (i == s["answer_index"])
                    pts = 3 if ok else 1
                    st.session_state.points += pts
                    st.session_state.game_results.append({"title":"Saving Choice","choice":lab,"correct":ok,"points":pts})
                    fb = "قرار رائع! +" + str(pts) + " نقاط" if ok else "موفق! نتعلم من التجربة. " + s["explain"]
                    st.info(fb)
                    if len(st.session_state.game_results) >= 1 and len(st.session_state.chat) >= 4:
                        st.session_state.parent_prompted = True
        st.markdown('</div>', unsafe_allow_html=True)

    # chat_input (Streamlit يمسحه تلقائياً بعد الإرسال)
    user_msg = st.chat_input("اكتب سؤالك هنا… (Enter للإرسال)")
    if user_msg:
        now = time.time()
        if now - st.session_state.cool_ts < 1.0:
            st.warning("خلك هادي… أرسل بعد لحظات 👌")
        else:
            st.session_state.cool_ts = now
            st.session_state.pending = user_msg

    # معالجة pending مرة واحدة
    run_id = str(len(st.session_state.chat))
    if st.session_state.pending and st.session_state.run_id != run_id:
        txt = st.session_state.pending.strip()
        st.session_state.pending = None
        st.session_state.run_id = run_id
        if txt:
            st.session_state.chat.append(("user", txt))
            st.session_state.typing = True
            st.rerun()

    # إرسال فعلي
    if st.session_state.typing:
        last_user = None
        for r,c in reversed(st.session_state.chat):
            if r == "user":
                last_user = c; break
        reply = ask_masroofi(last_user or "")
        st.session_state.chat.append(("assistant", reply))
        st.session_state.typing = False
        st.rerun()

def page_parent():
    # شريط علوي: رجوع / تعديل
    b1,b2,b3 = st.columns([5,1,1])
    with b2:
        if st.button("⬅️ رجوع إلى MasroofiGPT"):
            st.session_state.nav = 1; st.rerun()
    with b3:
        if st.button("✏️ تعديل البيانات"):
            st.session_state.nav = 0; st.rerun()

    st.title("لوحة وليّ الأمر 📊")
    st.caption("نظرة شاملة + تقرير تربوي مالي + أدوات للطباعة.")

    # بطاقات أرقام
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("العمر", st.session_state.age)
    with c2: st.metric("آخر التفاعلات", len(st.session_state.chat))
    with c3: st.metric("الألغاز/الألعاب", len(st.session_state.riddles_results)+len(st.session_state.game_results))

    # ملاحظات
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📝 ملاحظات وليّ الأمر")
    st.text_area("اكتب ملاحظتك أو هدف الأسبوع (تدمج في التقرير):", key="parent_notes", height=100)
    cc1,cc2 = st.columns([1,1])
    if cc1.button("🔄 توليد/تحديث التقرير الآن"):
        make_parent_report(); st.success("تم توليد التقرير.")
    if cc2.button("🧹 مسح التقرير"):
        st.session_state.parent_report = ""; st.toast("تم المسح.")
    st.markdown('</div>', unsafe_allow_html=True)

    # مقتطفات
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("💬 مقتطفات حديثة")
    if st.session_state.chat:
        for role,content in st.session_state.chat[-6:]:
            who = "👦 طفل" if role=="user" else "🤖 مصروفي"
            st.write(f"**{who}:** {content}")
    else:
        st.info("لا توجد محادثات بعد.")
    st.markdown('</div>', unsafe_allow_html=True)

    # تقرير
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📄 تقرير وليّ الأمر (تحليل تربوي مالي)")
    if st.session_state.parent_report:
        st.markdown(st.session_state.parent_report)
    else:
        st.info("اضغط (توليد/تحديث التقرير) بالأعلى لكتابة تقرير رسمي.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Checklist
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📋 Checklist للطباعة")
    html = checklist_table(st.session_state.cycle, st.session_state.goal_choice)
    st.markdown(html, unsafe_allow_html=True)
    pdf = checklist_pdf(st.session_state.cycle, st.session_state.goal_choice)
    st.download_button("⬇️ تنزيل كـ PDF", data=pdf, file_name="masroofi_checklist.pdf", mime="application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)

    # شات مصغّر (اختياري)
    if st.session_state.show_mini_chat_in_parent:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("💬 مصروفي — شات مصغّر")
        mini = st.text_input("اكتب سؤالك هنا…", key="mini_in_parent")
        cA,cB = st.columns([1,2])
        if cA.button("إرسال"):
            if mini and mini.strip():
                st.session_state.chat.append(("user", mini.strip()))
                st.info("مصروفي يكتب…")
                st.session_state.chat.append(("assistant", ask_masroofi(mini.strip())))
                st.rerun()
        if cB.button("فتح الشات الرئيسي"):
            st.session_state.nav = 1; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# -------- Run ----------
top_nav()
if st.session_state.nav == 0:
    page_home()
elif st.session_state.nav == 1:
    page_gpt()
else:
    page_parent()