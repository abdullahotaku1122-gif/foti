"""Foti: personal routine app (Kivy). Desktop test: pip install kivy && python main.py"""
import datetime as dt
import json
import math
import os
import struct
import wave

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import ColorProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

BG = (.039, .039, .043, 1)      # carbon black
CARD = (.082, .086, .094, 1)
SOFT = (.145, .153, .169, 1)
BAR = (.30, .32, .36, 1)
ACC = (.76, .78, .82, 1)        # silver
TXT = (.93, .94, .95, 1)
MUT = (.55, .57, .61, 1)
DARK = (.04, .04, .045, 1)

# [id, name, every_second_day]
TASKS = [["sib", "Help my siblings study", 0], ["fruit", "Eat fruits", 0],
         ["dish", "Do the dishes (night)", 0], ["cal", "Calisthenics training", 0],
         ["wash", "Wash the clothes", 1], ["skill", "30 min: learn or train my skill", 0],
         ["study", "1.5 hours of study", 0]]
PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# name: (wave shape, [(Hz, seconds)]); 0 Hz is a rest. Synthesized on first run.
TONES = {
    "Rise": ("sine", [(523, .15), (659, .15), (784, .35)]),
    "Beep": ("square", [(880, .1), (0, .06), (880, .1), (0, .06), (880, .3)]),
    "Drop": ("triangle", [(392, .25), (330, .25), (262, .45)]),
    "Bounce": ("square", [(660, .12), (784, .12), (990, .12), (784, .12), (660, .25)]),
    "Chime": ("sine", [(440, .3), (554, .3), (659, .4)]),
    "Pulse": ("square", [(1000, .08), (0, .05), (1000, .08), (0, .05), (1000, .08), (0, .05), (1000, .3)]),
    "Climb": ("triangle", [(330, .2), (440, .2), (523, .2), (659, .2), (784, .4)]),
}

KV = """
<Card>:
    canvas.before:
        Color:
            rgba: self.bg
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
<Pill>:
    background_normal: ''
    background_color: 0, 0, 0, 0
    bold: True
    font_size: sp(14)
    canvas.before:
        Color:
            rgba: self.bg
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
"""


class Card(BoxLayout):
    bg = ColorProperty(CARD)


class Pill(Button):
    bg = ColorProperty(SOFT)


def due(day):
    return day.toordinal() % 2 == 0


def lbl(text, size=15, color=TXT, bold=False, align="left"):
    l = Label(text=text, font_size=sp(size), color=color, bold=bold,
              halign=align, valign="middle", size_hint_y=None)
    l.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
    l.bind(texture_size=lambda w, v: setattr(w, "height", v[1] + dp(6)))
    return l


def card(auto=True, **kw):
    c = Card(orientation="vertical", padding=dp(14), spacing=dp(8), size_hint_y=None, **kw)
    if auto:
        c.bind(minimum_height=c.setter("height"))
    return c


def pill(text, bg=SOFT, color=TXT, hint=1, h=44):
    return Pill(text=text, bg=bg, color=color, size_hint_x=hint, size_hint_y=None, height=dp(h))


def row(h=44, spacing=dp(8)):
    return BoxLayout(size_hint_y=None, height=dp(h), spacing=spacing)


def progress(frac):
    b = row(8, spacing=0)
    b.add_widget(Card(bg=ACC, size_hint_x=max(.001, frac)))
    b.add_widget(Card(bg=SOFT, size_hint_x=max(.001, 1 - frac)))
    return b


def make_wav(path, shape, pattern):
    rate, frames = 22050, bytearray()
    for f, d in pattern:
        n = int(rate * d)
        for i in range(n):
            v = 0.0
            if f:
                ph = (i * f / rate) % 1
                v = math.sin(2 * math.pi * ph) if shape == "sine" else (
                    (1 if ph < .5 else -1) if shape == "square" else 4 * abs(ph - .5) - 1)
                v *= min(1, i / (rate * .01), (n - i) / (rate * .02)) * .45
            frames += struct.pack("<h", int(v * 32767))
    frames += b"\x00\x00" * int(rate * .4)  # gap before the loop repeats
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


class Foti(App):
    title = "Foti"

    def build(self):
        Builder.load_string(KV)
        Window.clearcolor = BG
        Window.softinput_mode = "below_target"
        if platform not in ("android", "ios"):
            Window.size = (400, 700)
        self.today = dt.date.today()
        self.sound = self.snz = self.modal = None
        self.view = "today"
        self.load()
        for name, (shape, pat) in TONES.items():
            p = self.path(name + ".wav")
            if not os.path.exists(p):
                make_wav(p, shape, pat)
        root = BoxLayout(orientation="vertical")
        self.body = BoxLayout()
        root.add_widget(self.body)
        nav = BoxLayout(size_hint_y=None, height=dp(64), padding=dp(8), spacing=dp(6))
        self.nav = {}
        for k, t in (("today", "Today"), ("prayers", "Prayers"), ("week", "Week"), ("settings", "Settings")):
            b = pill(t, h=48)
            b.font_size = sp(13)
            b.bind(on_release=lambda *_, k=k: self.show(k))
            self.nav[k] = b
            nav.add_widget(b)
        root.add_widget(nav)
        Clock.schedule_interval(self.tick, 20)
        Window.bind(on_keyboard=self.on_key)
        self.show("today")
        return root

    def on_key(self, _w, key, *_a):
        if key == 27:  # Esc / Android back: go to Today before leaving the app
            if self.modal:
                return True
            if self.view != "today":
                self.show("today")
                return True
        return False

    def on_pause(self):
        return True

    def on_stop(self):
        self.stop_sound()

    # ---- data ----
    def path(self, name):
        return os.path.join(self.user_data_dir, name)

    def load(self):
        key = self.today.isoformat()
        self.d = {"day": key, "done": [], "pr": [], "last": "", "tones": {}, "hist": {},
                  "tasks": [list(t) for t in TASKS], "cfg": {"on": True, "h": 21, "m": 30, "snz": 5, "rep": True}}
        try:
            with open(self.path("foti.json")) as f:
                self.d.update(json.load(f))
        except Exception:
            pass
        self.d["cfg"] = {"on": True, "h": 21, "m": 30, "snz": 5, "rep": True, **self.d["cfg"]}
        self.d.setdefault("last", "")
        if self.d["day"] != key:
            self.d.update(day=key, done=[], pr=[], last="")
        for i, t in enumerate(self.d["tasks"]):
            self.d["tones"].setdefault(t[0], list(TONES)[i % len(TONES)])
        self.save()

    def todays(self):
        return [t for t in self.d["tasks"] if not t[2] or due(self.today)]

    def left(self):
        return [t for t in self.todays() if t[0] not in self.d["done"]]

    def save(self):
        self.d["hist"][self.today.isoformat()] = [
            len(self.d["done"]) + len(self.d["pr"]), len(self.todays()) + 5]
        try:
            with open(self.path("foti.json"), "w") as f:
                json.dump(self.d, f)
        except Exception:
            pass

    def refresh(self):
        self.save()
        self.show(self.view)

    def toggle(self, key, v):
        lst = self.d[key]
        lst.remove(v) if v in lst else lst.append(v)
        self.refresh()

    def set_tone(self, tid, name):
        self.d["tones"][tid] = name
        self.play(name, False)
        self.refresh()

    def cfg_set(self, key, val):
        self.d["cfg"][key] = val
        self.refresh()

    def shift_time(self, dm):
        c = self.d["cfg"]
        mins = (c["h"] * 60 + c["m"] + dm) % 1440
        c["h"], c["m"] = divmod(mins, 60)
        self.refresh()

    def add_task(self, name):
        name = name.strip()
        if name:
            tid = dt.datetime.now().strftime("c%H%M%S%f")
            self.d["tasks"].append([tid, name[:60], 0])
            self.d["tones"][tid] = list(TONES)[(len(self.d["tasks"]) - 1) % len(TONES)]
            self.refresh()

    def remove_task(self, tid):
        self.d["tasks"] = [t for t in self.d["tasks"] if t[0] != tid]
        self.d["done"] = [x for x in self.d["done"] if x != tid]
        self.refresh()

    def reset_today(self):
        self.d.update(done=[], pr=[], last="")
        self.refresh()

    def streak(self):
        n, day = 0, self.today
        while True:
            v = self.d["hist"].get(day.isoformat())
            if v and v[1] and v[0] >= v[1]:
                n += 1
            elif day != self.today:
                return n
            day -= dt.timedelta(days=1)

    # ---- timing ----
    def tick(self, _dt):
        now = dt.datetime.now()
        if now.date() != self.today:  # midnight rollover
            self.today = now.date()
            self.load()
            self.show(self.view)
            return
        c, last = self.d["cfg"], self.d["last"]
        if not c["on"] or self.modal or self.snz or (now.hour, now.minute) < (c["h"], c["m"]):
            return
        if last and (not c["rep"] or now - dt.datetime.fromisoformat(last) < dt.timedelta(minutes=30)):
            return
        left = self.left()
        if left:
            self.d["last"] = now.isoformat()
            self.save()
            self.ring(left[0][0])

    # ---- sound and alarm ----
    def play(self, name, loop):
        self.stop_sound()
        try:
            s = SoundLoader.load(self.path(name + ".wav"))
        except Exception:
            s = None
        if s:
            s.loop = loop
            s.play()
            self.sound = s

    def stop_sound(self):
        if self.sound:
            self.sound.stop()
            self.sound.unload()
            self.sound = None

    def ring(self, tid):
        self.stop_alarm()
        name = next((t[1] for t in self.d["tasks"] if t[0] == tid), "Reminder")
        left = [t[1] for t in self.left()]
        m = ModalView(size_hint=(1, 1), auto_dismiss=False, background="",
                      background_color=(.02, .02, .025, 1))
        c = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(12))
        c.add_widget(Widget())
        c.add_widget(lbl(name, 30, TXT, True, "center"))
        c.add_widget(lbl("Do it now. Don't sleep before it's done.", 18, ACC, False, "center"))
        c.add_widget(lbl("Still left today: " + (", ".join(left) or "nothing else"), 14, MUT, False, "center"))
        self.play(self.d["tones"].get(tid, "Beep"), True)
        if not self.sound:
            c.add_widget(lbl("Sound is unavailable on this device.", 12, MUT, False, "center"))
        c.add_widget(Widget())
        done = pill("Mark done", ACC, DARK, h=60)
        done.bind(on_release=lambda *_: (self.d["done"].append(tid) if tid not in self.d["done"] else None,
                                         self.stop_alarm(), self.refresh()))
        c.add_widget(done)
        r = row(60, spacing=dp(12))
        sn = pill(f"Snooze {self.d['cfg']['snz']} min", SOFT, TXT, h=60)
        st = pill("Stop", SOFT, TXT, h=60)
        sn.bind(on_release=lambda *_: self.snooze(tid))
        st.bind(on_release=lambda *_: self.stop_alarm())
        r.add_widget(sn)
        r.add_widget(st)
        c.add_widget(r)
        m.add_widget(c)
        self.modal = m
        m.open()

    def stop_alarm(self):
        self.stop_sound()
        if self.snz:
            self.snz.cancel()
            self.snz = None
        if self.modal:
            self.modal.dismiss()
            self.modal = None

    def snooze(self, tid):
        self.stop_alarm()
        self.snz = Clock.schedule_once(lambda _d: self.ring(tid), self.d["cfg"]["snz"] * 60)

    def pick_tone(self, tid):
        m = ModalView(size_hint=(.86, None), height=dp(70 + 52 * len(TONES)), background="",
                      background_color=CARD)
        c = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        c.add_widget(lbl("Choose a tone", 17, TXT, True))
        for name in TONES:
            on = self.d["tones"][tid] == name
            b = pill(name, ACC if on else SOFT, DARK if on else TXT)
            b.bind(on_release=lambda *_, n=name: (m.dismiss(), self.set_tone(tid, n)))
            c.add_widget(b)
        m.add_widget(c)
        m.open()

    # ---- screens ----
    def show(self, view):
        self.view = view
        self.body.clear_widgets()
        for k, b in self.nav.items():
            b.bg, b.color = (ACC, DARK) if k == view else (SOFT, TXT)
        sv = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(16), spacing=dp(10))
        box.bind(minimum_height=box.setter("height"))
        sv.add_widget(box)
        self.body.add_widget(sv)
        h = dt.datetime.now().hour
        hello = "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"
        box.add_widget(lbl("Foti", 32, ACC, True))
        box.add_widget(lbl(f"{hello}. {self.today.strftime('%A, %d %B')}", 14, MUT))
        getattr(self, "v_" + view)(box)

    def v_today(self, box):
        tasks, left = self.todays(), self.left()
        total, done = len(tasks) + 5, len(self.d["done"]) + len(self.d["pr"])
        box.add_widget(lbl(f"{done} of {total} done today", 14, MUT))
        box.add_widget(progress(done / total))
        b = card(bg=(.12, .125, .135, 1))
        if left:
            b.add_widget(lbl(f"{len(left)} left today", 17, ACC, True))
            b.add_widget(lbl(", ".join(t[1] for t in left) + ". Finish them before you sleep.", 14, TXT))
        else:
            b.add_widget(lbl("All tasks done", 17, ACC, True))
            b.add_widget(lbl("Nothing left. You can sleep.", 14, MUT))
        b.add_widget(lbl(f"Prayers: {len(self.d['pr'])} of 5", 13, MUT))
        box.add_widget(b)
        if not tasks:
            box.add_widget(lbl("No tasks yet. Add one in Settings.", 14, MUT))
        for t in tasks:
            tid, on = t[0], t[0] in self.d["done"]
            c = card()
            c.add_widget(lbl(t[1], 16, MUT if on else TXT, True))
            r = row()
            tone = pill("Tone: " + self.d["tones"][tid], hint=.4)
            tone.bind(on_release=lambda *_, tid=tid: self.pick_tone(tid))
            test = pill("Test", hint=.2)
            test.bind(on_release=lambda *_, tid=tid: self.ring(tid))
            tog = pill("Done" if on else "Mark done", SOFT if on else ACC, ACC if on else DARK, .4)
            tog.bind(on_release=lambda *_, tid=tid: self.toggle("done", tid))
            for w in (tone, test, tog):
                r.add_widget(w)
            c.add_widget(r)
            box.add_widget(c)
        box.add_widget(lbl("Washing comes up every second day.", 12, MUT))

    def v_prayers(self, box):
        n = len(self.d["pr"])
        box.add_widget(lbl(f"{n} of 5 prayed today. No alerts, just tick what you have prayed.", 14, MUT))
        box.add_widget(progress(n / 5))
        for p in PRAYERS:
            on = p in self.d["pr"]
            c = card()
            r = row()
            name = lbl(p, 17, TXT, True)
            name.size_hint_x = .6
            name.pos_hint = {"center_y": .5}
            tog = pill("Prayed" if on else "Mark prayed", SOFT if on else ACC, ACC if on else DARK, .4)
            tog.bind(on_release=lambda *_, p=p: self.toggle("pr", p))
            r.add_widget(name)
            r.add_widget(tog)
            c.add_widget(r)
            box.add_widget(c)

    def v_week(self, box):
        dow, hist = self.today.weekday(), self.d["hist"]
        rows = []
        for i, n in enumerate(DAYS):
            v = hist.get((self.today - dt.timedelta(days=dow - i)).isoformat(), [0, 0])
            rows.append((n, v[0], v[1]))
        past = [r for r in rows[:dow] if r[2]]
        sd = sum(r[1] for r in rows[:dow + 1])
        st = sum(r[2] for r in rows[:dow + 1])
        missed = sum(r[2] - r[1] for r in past)
        rt = lambda r: r[1] / r[2]
        best = max(past, key=rt)[0] if past else "-"
        worst = min(past, key=rt)[0] if past else "-"
        box.add_widget(lbl("Prayers and tasks together. Foti fills this in as you use it.", 13, MUT))
        g = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(272),
                       row_default_height=dp(84), row_force_default=True)
        for val, name in ((str(sd), "done this week"), (str(missed), "missed"),
                          (f"{round(100 * sd / st) if st else 0}%", "completed"),
                          (f"{self.streak()} day" + ("" if self.streak() == 1 else "s"), "full-day streak"),
                          (best, "best day"), (worst, "weakest day")):
            c = card(False)
            c.height = dp(84)
            c.add_widget(lbl(val, 26, ACC, True))
            c.add_widget(lbl(name, 13, MUT))
            g.add_widget(c)
        box.add_widget(g)
        wrap = card(False)
        wrap.height = dp(190)
        bars = BoxLayout(spacing=dp(8))
        for i, (n, done, total) in enumerate(rows):
            r = max(.03, done / total) if total else .03
            col = BoxLayout(orientation="vertical")
            col.add_widget(Widget(size_hint_y=1 - r))
            col.add_widget(Card(bg=ACC if i == dow else BAR, size_hint_y=r))
            col.add_widget(lbl(n, 12, MUT, False, "center"))
            bars.add_widget(col)
        wrap.add_widget(bars)
        box.add_widget(wrap)

    def v_settings(self, box):
        cfg = self.d["cfg"]
        c = card()
        c.add_widget(lbl("Evening check", 16, TXT, True))
        c.add_widget(lbl("If tasks are still left at this time, Foti rings an alarm for the first one. "
                         "Works while the app is open.", 12, MUT))
        r = row()
        t = lbl(f"{cfg['h']:02d}:{cfg['m']:02d}", 22, ACC, True)
        t.size_hint_x = .32
        t.pos_hint = {"center_y": .5}
        r.add_widget(t)
        for txt, dm in (("-15", -15), ("+15", 15)):
            b = pill(txt, hint=.2)
            b.bind(on_release=lambda *_, dm=dm: self.shift_time(dm))
            r.add_widget(b)
        sw = pill("On" if cfg["on"] else "Off", ACC if cfg["on"] else SOFT, DARK if cfg["on"] else TXT, .28)
        sw.bind(on_release=lambda *_: self.cfg_set("on", not cfg["on"]))
        r.add_widget(sw)
        c.add_widget(r)
        rp = pill("Repeat every 30 min until done: " + ("On" if cfg["rep"] else "Off"),
                  ACC if cfg["rep"] else SOFT, DARK if cfg["rep"] else TXT)
        rp.font_size = sp(13)
        rp.bind(on_release=lambda *_: self.cfg_set("rep", not cfg["rep"]))
        c.add_widget(rp)
        box.add_widget(c)

        c = card()
        c.add_widget(lbl("Snooze length", 16, TXT, True))
        sz = pill(f"{cfg['snz']} minutes (tap to change)")
        sz.bind(on_release=lambda *_: self.cfg_set("snz", {5: 10, 10: 15}.get(cfg["snz"], 5)))
        c.add_widget(sz)
        box.add_widget(c)

        c = card()
        c.add_widget(lbl("Add a task", 16, TXT, True))
        r = row()
        ti = TextInput(hint_text="New task", multiline=False, size_hint_x=.68, background_normal="",
                       background_active="", background_color=SOFT, foreground_color=TXT,
                       hint_text_color=MUT, cursor_color=ACC, padding=[dp(12), dp(12)], font_size=sp(15))
        ti.bind(on_text_validate=lambda w: self.add_task(w.text))
        add = pill("Add", ACC, DARK, .32)
        add.bind(on_release=lambda *_: self.add_task(ti.text))
        r.add_widget(ti)
        r.add_widget(add)
        c.add_widget(r)
        box.add_widget(c)

        c = card()
        c.add_widget(lbl("Your tasks", 16, TXT, True))
        for tk in self.d["tasks"]:
            r = row()
            n = lbl(tk[1], 14, TXT)
            n.size_hint_x = .68
            n.pos_hint = {"center_y": .5}
            rm = pill("Remove", hint=.32)
            rm.bind(on_release=lambda *_, tid=tk[0]: self.remove_task(tid))
            r.add_widget(n)
            r.add_widget(rm)
            c.add_widget(r)
        box.add_widget(c)

        rs = pill("Reset today's progress")
        rs.bind(on_release=lambda *_: self.reset_today())
        box.add_widget(rs)


if __name__ == "__main__":
    Foti().run()