"""
🎁 Ebic Gift — mashq loyihasi (backend + bot bitta faylda)
Ishga tushirish:
  pip install aiogram fastapi uvicorn pydantic
  python main.py
Eslatma: Mini App uchun WEBAPP_URL https:// bo'lishi shart (ngrok/cloudflare tunnel)
"""
import asyncio, json, random, sqlite3
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                           LabeledPrice, PreCheckoutQuery, MenuButtonWebApp, WebAppInfo)
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

TOKEN = "TOKENINGIZNI_QOYING"
BOT_NAME = "Epic Global Training"
WEBAPP_URL = "https://SIZNING_DARMONLI_HAVOLA.uz"   # <-- o'zgartiring (https shart!)

REF_PERCENT = 10               # referral depozitdan %
TON_PER_STAR = 100000 / 15     # 15 Stars = 100,000 TON (skrinshotdagi kurs)
MIN_STARS, MAX_STARS = 15, 1000
MIN_TRANSFER = 0.10

bot = Bot(token=TOKEN)
dp = Dispatcher()
db = sqlite3.connect("epic_global.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users(
 user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, tickets INTEGER DEFAULT 0,
 referrer INTEGER DEFAULT 0, referrals INTEGER DEFAULT 0, ref_earned REAL DEFAULT 0,
 last_daily TEXT DEFAULT '', task_date TEXT DEFAULT '',
 t_rocket INTEGER DEFAULT 0, t_plinko INTEGER DEFAULT 0, t_box INTEGER DEFAULT 0,
 t_pvp INTEGER DEFAULT 0, t_upgrade INTEGER DEFAULT 0, claimed TEXT DEFAULT '{}',
 last_free TEXT DEFAULT '', last_free24 TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS gifts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, emoji TEXT, name TEXT, value REAL);
CREATE TABLE IF NOT EXISTS battles(
 id INTEGER PRIMARY KEY AUTOINCREMENT, bet REAL, p1 INTEGER, p2 INTEGER,
 winner INTEGER DEFAULT 0, status TEXT DEFAULT 'waiting');
CREATE TABLE IF NOT EXISTS giveaways(
 id INTEGER PRIMARY KEY, name TEXT, gifts TEXT, ticket_pool INTEGER DEFAULT 0,
 ends_at TEXT, winners TEXT DEFAULT '[]', active INTEGER DEFAULT 1);
""")

BOXES = [
 {"id":"peach","name":"Peach","price":8,"img":"🍑"},
 {"id":"cap","name":"Cap","price":15,"img":"🧢"},
 {"id":"ring","name":"Ring","price":15,"img":"💍"},
 {"id":"epic","name":"Epic","price":40,"img":"🐸"},
 {"id":"vip","name":"VIP","price":50,"img":"👑"},
 {"id":"elite","name":"Elite","price":125,"img":"💎"},
]
BOX_POOLS = {
 "peach":[("🍑","Juicy Peach",5,40),("🐸","Plush Pepe",12,35),("🧢","Cap",15,20),("💍","Ring",25,5)],
 "cap":[("🧢","Cap",15,30),("🐸","Plush Pepe",12,30),("💍","Ring",25,20),("⌚","Swiss Watch",35,12),("🎁","Epic Set",45,8)],
 "ring":[("💍","Ring",25,30),("⌚","Swiss Watch",35,25),("🎁","Epic Set",45,20),("👑","VIP Crown",60,15),("💎","Diamond",90,10)],
 "epic":[("🎁","Epic Set",45,35),("👑","VIP Crown",60,25),("💎","Diamond",90,15),("🚀","Rocket Toy",120,10),("🏆","Golden Trophy",200,5),("🍑","Juicy Peach",5,10)],
 "vip":[("👑","VIP Crown",60,35),("💎","Diamond",90,25),("🚀","Rocket Toy",120,20),("🏆","Golden Trophy",200,12),("🛸","UFO",350,8)],
 "elite":[("💎","Diamond",90,30),("🚀","Rocket Toy",120,25),("🏆","Golden Trophy",200,20),("🛸","UFO",350,15),("🌟","Legendary Star",600,10)],
}
TASKS = [
 {"key":"daily","name":"Daily check-in","reward":10,"icon":"📅","need":1},
 {"key":"rocket","name":"Play 3 rocket rounds","reward":25,"icon":"🚀","need":3},
 {"key":"plinko","name":"Drop 10 balls in Plinko","reward":25,"icon":"🔵","need":10},
 {"key":"box","name":"Open a gift box","reward":15,"icon":"🎁","need":1},
 {"key":"pvp","name":"Play a PvP round","reward":25,"icon":"⚔️","need":1},
 {"key":"upgrade","name":"Play an Upgrade round","reward":15,"icon":"⬆️","need":1},
]
COUNTERS = {"rocket":"t_rocket","plinko":"t_plinko","box":"t_box","pvp":"t_pvp","upgrade":"t_upgrade"}
PLINKO_TABLE = [5,2,1.2,0.7,0.4,0.7,1.2,2,5]


def get_user(uid):
    db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
    u = db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    if u["task_date"] != date.today().isoformat():
        db.execute("""UPDATE users SET task_date=?, t_rocket=0,t_plinko=0,t_box=0,
                      t_pvp=0,t_upgrade=0 WHERE user_id=?""",
                   (date.today().isoformat(), uid))
        db.commit()
        u = db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    return u


def mask(uid):
    s = str(uid)
    return f"{s[:2]}***{s[-2:]}"


def roll(pool):
    items, weights = zip(*[(p[:3], p[3]) for p in pool])
    return random.choices(items, weights=weights)[0]


# ================= BOT (aiogram) =================
@dp.message(Command("start"))
async def cmd_start(m: Message, command: CommandObject):
    uid = m.from_user.id
    u = get_user(uid)
    if command.args and command.args.startswith("ref_") and u["referrer"] == 0:
        try:
            ref = int(command.args[4:])
        except ValueError:
            ref = 0
        if ref and ref != uid:
            db.execute("UPDATE users SET referrer=? WHERE user_id=?", (ref, uid))
            db.execute("UPDATE users SET referrals=referrals+1 WHERE user_id=?", (ref,))
            db.commit()
            try:
                await bot.send_message(ref, f"🎉 {m.from_user.first_name} sizning havolangiz orqali qo'shildi!")
            except Exception:
                pass
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎁 Epic Globalni ochish",
                             web_app=WebAppInfo(url=WEBAPP_URL))]])
    await m.answer("Epic Global Training — xush kelibsiz! 🎁", reply_markup=kb)


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    ok = q.currency == "XTR" and MIN_STARS <= q.total_amount <= MAX_STARS
    await q.answer(ok=ok, error_message=None if ok else f"{MIN_STARS}-{MAX_STARS} Stars")


@dp.message(F.successful_payment)
async def payment_ok(m: Message):
    stars = int(m.successful_payment.invoice_payload.split("_")[1])
    ton = round(stars * TON_PER_STAR, 2)
    uid = m.from_user.id
    u = get_user(uid)
    db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (ton, uid))
    if u["referrer"]:
        ref_bonus = round(ton * REF_PERCENT / 100, 2)
        db.execute("""UPDATE users SET ref_earned=ref_earned+?, balance=balance+?
                      WHERE user_id=?""", (ref_bonus, ref_bonus, u["referrer"]))
        db.commit()
        try:
            await bot.send_message(u["referrer"],
                f"💰 Referral depozitidan +{ref_bonus:,.2f} TON ({REF_PERCENT}%)")
        except Exception:
            pass
    db.commit()
    await m.answer(f"✅ Depozit qabul qilindi: +{ton:,.2f} TON")


# ================= API (FastAPI) =================
app = FastAPI()

class Transfer(BaseModel):
    user_id: int; to: str; amount: float
class DepositStars(BaseModel):
    user_id: int; stars: int
class BoxOpen(BaseModel):
    user_id: int; box: str
class Bet(BaseModel):
    user_id: int; bet: float
class PvpJoin(BaseModel):
    user_id: int; bet: float
class Upgrade(BaseModel):
    user_id: int; gift_id: int; target: float
class GiveawayJoin(BaseModel):
    user_id: int; gid: int
class TaskClaim(BaseModel):
    user_id: int; key: str
class SendGift(BaseModel):
    user_id: int; gift_id: int; to: str
class MockDeposit(BaseModel):   # MASHQ UCHUN (real TON emas!)
    user_id: int; amount: float


@app.get("/")
def index():
    return FileResponse("miniapp.html")


@app.get("/api/me")
def me(user_id: int):
    u = get_user(user_id)
    claimed = json.loads(u["claimed"])
    inv = db.execute("SELECT * FROM gifts WHERE user_id=?", (user_id,)).fetchall()
    tasks = []
    for t in TASKS:
        prog = 1 if (t["key"] == "daily" and u["last_daily"] == date.today().isoformat()) \
               else (0 if t["key"] == "daily" else u[COUNTERS[t["key"]]])
        tasks.append({**t, "progress": min(prog, t["need"]), "claimed": t["key"] in claimed})
    return {"balance": round(u["balance"], 2), "tickets": u["tickets"],
            "referrals": u["referrals"], "ref_earned": round(u["ref_earned"], 2),
            "tasks": tasks, "inventory": [dict(g) for g in inv]}


@app.post("/api/daily")
def daily(d: Bet):
    u = get_user(d.user_id)
    today = date.today().isoformat()
    if u["last_daily"] == today:
        return {"error": "Bugungi bonus allaqachon olingan!"}
    db.execute("UPDATE users SET balance=balance+500, tickets=tickets+10, last_daily=? WHERE user_id=?",
               (today, d.user_id))
    db.commit()
    return {"ok": True, "message": "+500 TON va +10 tickets!"}


@app.post("/api/transfer")
def transfer(t: Transfer):
    u = get_user(t.user_id)
    if t.amount < MIN_TRANSFER:
        return {"error": f"Minimal {MIN_TRANSFER} TON"}
    if u["balance"] < t.amount:
        return {"error": "Balans yetarli emas!"}
    try:
        to_id = int(t.to.replace("@", ""))
    except ValueError:
        return {"error": "ID noto'g'ri (raqam kiriting)"}
    get_user(to_id)
    db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (t.amount, t.user_id))
    db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (t.amount, to_id))
    db.commit()
    return {"ok": True, "balance": round(u["balance"] - t.amount, 2)}


@app.post("/api/deposit/stars")
async def dep_stars(d: DepositStars):
    if not (MIN_STARS <= d.stars <= MAX_STARS):
        return JSONResponse({"error": f"{MIN_STARS}-{MAX_STARS} Stars"}, 400)
    await bot.send_invoice(
        chat_id=d.user_id,
        title=f"💳 {d.stars} Stars depozit",
        description=f"{d.stars} Stars = {d.stars * TON_PER_STAR:,.0f} TON",
        payload=f"deposit_{d.stars}", currency="XTR",
        prices=[LabeledPrice(label=f"{d.stars} Stars", amount=d.stars)])
    return {"ok": True}


@app.post("/api/deposit/mock")
def dep_mock(d: MockDeposit):   # MASHQ UCHUN
    if d.amount < 0.05:
        return {"error": "Minimal 0.05 TON"}
    get_user(d.user_id)
    db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (d.amount, d.user_id))
    db.commit()
    return {"ok": True, "message": f"(Mashq) +{d.amount} TON"}


@app.get("/api/boxes")
def boxes():
    return BOXES


@app.post("/api/box/open")
def box_open(b: BoxOpen):
    u = get_user(b.user_id)
    box = next((x for x in BOXES if x["id"] == b.box), None)
    if not box:
        return {"error": "Bunday quti yo'q"}
    if u["balance"] < box["price"]:
        return {"error": "Balans yetarli emas!"}
    emoji, name, value = roll(BOX_POOLS[b.box])
    db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (box["price"], b.user_id))
    db.execute("INSERT INTO gifts(user_id,emoji,name,value) VALUES(?,?,?,?)",
               (b.user_id, emoji, name, value))
    db.execute("UPDATE users SET t_box=t_box+1 WHERE user_id=?", (b.user_id,))
    db.commit()
    return {"ok": True, "emoji": emoji, "name": name, "value": value,
            "balance": round(u["balance"] - box["price"], 2)}


@app.post("/api/box/free")
def box_free(b: BoxOpen):
    u = get_user(b.user_id)
    today = date.today().isoformat()
    col = "last_free24" if b.box == "free24" else "last_free"
    if u[col] == today:
        return {"error": "Bugungi bepul quti allaqachon olingan!"}
    pool = BOX_POOLS["cap" if b.box == "free24" else "peach"]
    emoji, name, value = roll(pool)
    db.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (today, b.user_id))
    db.execute("INSERT INTO gifts(user_id,emoji,name,value) VALUES(?,?,?,?)",
               (b.user_id, emoji, name, value))
    db.commit()
    return {"ok": True, "emoji": emoji, "name": name, "value": value}


@app.post("/api/game/rocket")
def rocket(bet: Bet):
    u = get_user(bet.user_id)
    if u["balance"] < bet.bet:
        return {"error": "Balans yetarli emas!"}
    crash = round(max(1.0, 0.98 / max(random.random(), 0.01)), 2)
    mult = 1.2
    win = crash >= mult
    payout = round(bet.bet * mult, 2) if win else 0
    db.execute("UPDATE users SET balance=balance-?, t_rocket=t_rocket+1 WHERE user_id=?",
               (bet.bet, bet.user_id))
    if win:
        db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (payout, bet.user_id))
    db.commit()
    return {"crash": crash, "win": win, "payout": payout,
            "balance": round(u["balance"] - bet.bet + payout, 2)}


@app.post("/api/game/plinko")
def plinko(bet: Bet):
    u = get_user(bet.user_id)
    if u["balance"] < bet.bet:
        return {"error": "Balans yetarli emas!"}
    k = sum(1 for _ in range(8) if random.random() < 0.5)
    mult = PLINKO_TABLE[k]
    payout = round(bet.bet * mult, 2)
    db.execute("UPDATE users SET balance=balance-?, t_plinko=t_plinko+1 WHERE user_id=?",
               (bet.bet, bet.user_id))
    db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (payout, bet.user_id))
    db.commit()
    return {"slot": k, "multiplier": mult, "payout": payout,
            "balance": round(u["balance"] - bet.bet + payout, 2)}


@app.post("/api/game/pvp")
def pvp(j: PvpJoin):
    u = get_user(j.user_id)
    if u["balance"] < j.bet:
        return {"error": "Balans yetarli emas!"}
    battle = db.execute("""SELECT * FROM battles WHERE bet=? AND status='waiting'
                           AND p1!=? ORDER BY id LIMIT 1""", (j.bet, j.user_id)).fetchone()
    if battle:
        winner, loser = (battle["p1"], j.user_id) if random.random() < 0.5 else (j.user_id, battle["p1"])
        prize = round(j.bet * 2 * 0.95, 2)
        db.execute("UPDATE battles SET p2=?, winner=?, status='done' WHERE id=?",
                   (j.user_id, winner, battle["id"]))
        db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (j.bet, j.user_id))
        db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (prize, winner))
        db.execute("UPDATE users SET t_pvp=t_pvp+1 WHERE user_id=?", (j.user_id,))
        db.commit()
        for pid, msg in ((winner, f"🏆 PVP g'alaba! +{prize} TON"),
                         (loser, "😢 PVP mag'lubiyat")):
            try:
                asyncio.get_event_loop().create_task(bot.send_message(pid, msg))
            except Exception:
                pass
        return {"status": "done", "win": winner == j.user_id, "prize": prize}
    db.execute("INSERT INTO battles(bet,p1) VALUES(?,?)", (j.bet, j.user_id))
    db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (j.bet, j.user_id))
    db.commit()
    return {"status": "waiting"}


@app.post("/api/game/upgrade")
def upgrade(g: Upgrade):
    u = get_user(g.user_id)
    gift = db.execute("SELECT * FROM gifts WHERE id=? AND user_id=?",
                      (g.gift_id, g.user_id)).fetchone()
    if not gift:
        return {"error": "Sovg'a topilmadi!"}
    if g.target <= gift["value"]:
        return {"error": "Target qiymat kattaroq bo'lishi kerak!"}
    chance = gift["value"] / g.target
    win = random.random() < chance
    db.execute("DELETE FROM gifts WHERE id=?", (g.gift_id,))
    result_emoji, result_name = "💨", "Yo'qotildi"
    if win:
        result_emoji, result_name = "✨", f"Upgraded {g.target}"
        db.execute("INSERT INTO gifts(user_id,emoji,name,value) VALUES(?,?,?,?)",
                   (g.user_id, "💎", result_name, g.target))
    db.execute("UPDATE users SET t_upgrade=t_upgrade+1 WHERE user_id=?", (g.user_id,))
    db.commit()
    return {"ok": True, "win": win, "chance": round(chance * 100, 1),
            "emoji": result_emoji, "name": result_name}


@app.post("/api/task/claim")
def task_claim(tc: TaskClaim):
    u = get_user(tc.user_id)
    task = next((t for t in TASKS if t["key"] == tc.key), None)
    if not task:
        return {"error": "Task topilmadi"}
    claimed = json.loads(u["claimed"])
    if tc.key in claimed:
        return {"error": "Allaqachon olgansiz!"}
    prog = 1 if (tc.key == "daily" and u["last_daily"] == date.today().isoformat()) \
           else (0 if tc.key == "daily" else u[COUNTERS[tc.key]])
    if prog < task["need"]:
        return {"error": f"Hali {task['need'] - prog} ta qoldi!"}
    claimed[tc.key] = date.today().isoformat()
    db.execute("UPDATE users SET tickets=tickets+?, claimed=? WHERE user_id=?",
               (task["reward"], json.dumps(claimed), tc.user_id))
    db.commit()
    return {"ok": True, "reward": task["reward"]}


@app.post("/api/gift/send")
def gift_send(s: SendGift):
    gift = db.execute("SELECT * FROM gifts WHERE id=? AND user_id=?",
                      (s.gift_id, s.user_id)).fetchone()
    if not gift:
        return {"error": "Sovg'a topilmadi!"}
    try:
        to_id = int(s.to.replace("@", ""))
    except ValueError:
        return {"error": "ID noto'g'ri"}
    get_user(to_id)
    db.execute("UPDATE gifts SET user_id=? WHERE id=?", (to_id, s.gift_id))
    db.commit()
    return {"ok": True}


@app.get("/api/leaderboard")
def leaderboard():
    rows = db.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10").fetchall()
    return [{"name": mask(r["user_id"]), "balance": round(r["balance"], 2)} for r in rows]


@app.get("/api/giveaways")
def giveaways():
    rows = db.execute("SELECT * FROM giveaways WHERE active=1").fetchall()
    return [{"id": r["id"], "name": r["name"], "gifts": json.loads(r["gifts"]),
             "ticket_pool": r["ticket_pool"],
             "ends_in": max(0, int((datetime.fromisoformat(r["ends_at"]) - datetime.now()).total_seconds()))}
            for r in rows]


@app.post("/api/giveaway/join")
def giveaway_join(gj: GiveawayJoin):
    u = get_user(gj.user_id)
    gw = db.execute("SELECT * FROM giveaways WHERE id=? AND active=1", (gj.gid,)).fetchone()
    if not gw:
        return {"error": "Giveaway topilmadi"}
    db.execute("UPDATE giveaways SET ticket_pool=ticket_pool+? WHERE id=?",
               (u["tickets"], gj.gid))
    db.commit()
    return {"ok": True}


@app.post("/api/giveaway/draw")   # admin: g'oliblarni aniqlash (mashq)
def giveaway_draw(gj: GiveawayJoin):
    gw = db.execute("SELECT * FROM giveaways WHERE id=? AND active=1", (gj.gid,)).fetchone()
    if not gw:
        return {"error": "Giveaway topilmadi"}
    users = [r["user_id"] for r in db.execute("SELECT user_id FROM users").fetchall()]
    winners = random.sample(users, min(50, len(users))) if users else []
    db.execute("UPDATE giveaways SET active=0, winners=? WHERE id=?",
               (json.dumps(winners), gj.gid))
    db.commit()
    return {"ok": True, "winners": winners}


@app.on_event("startup")
async def startup():
    if not db.execute("SELECT id FROM giveaways").fetchone():
        db.execute("INSERT INTO giveaways VALUES(1,'All Gifts',?,0,?,'[]',1)", (
            json.dumps([{"emoji": "🐸", "name": "Plush Pepe"}] * 3),
            (datetime.now() + timedelta(hours=12, minutes=41)).isoformat()))
        db.commit()
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
        text="🎁 Epic Global", web_app=WebAppInfo(url=WEBAPP_URL)))
    asyncio.create_task(dp.start_polling(bot))
    print("✅ Bot va API ishga tushdi!")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

