"""Generate deterministic seed data for PetCare MySQL database.

Produces seed.sql with realistic pet-hospital business data:
- 8 doctors (fixed roster, stable for interviews)
- 30 owners, 50 pets (species spread: cat/dog/bird/rabbit/hamster/reptile)
- ~340 appointments across 9 months (recent 3 months denser)
- ~250 medical records
- 500 bills (income analysis core)

Time consistency: everything is derived from AS_OF_DATE (default 2026-04-30),
the business analysis reference date (data ends on this day):
- DATA_START    = fixed 2025-08-01 (9-month data window, keeps data scale stable)
- DATA_END      = AS_OF_DATE                      (2026-04-30)
- RECENT_START  = month start of AS_OF_DATE - 2 months (2026-02-01, "recent 3 months")
- pets.birth_date <= DATA_END, created_at >= birth_date, created_at <= DATA_END

Deterministic: random.seed(42) -> same output on every run.
Override AS_OF_DATE with env var PETCARE_AS_OF_DATE (YYYY-MM-DD).
"""

import os
import random
from datetime import date, timedelta

random.seed(42)

AS_OF_DATE_STR = os.getenv("PETCARE_AS_OF_DATE", "2026-04-30")


def _parse_as_of_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SystemExit(f"invalid PETCARE_AS_OF_DATE '{raw}': expected YYYY-MM-DD") from exc


def add_months(d: date, months: int) -> date:
    """Add months with day clamping (e.g. 2026-05-31 -1M -> 2026-04-30)."""
    month_index = d.year * 12 + (d.month - 1) + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    if month == 2:
        last = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    elif month in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return date(year, month, min(d.day, last))


AS_OF_DATE = _parse_as_of_date(AS_OF_DATE_STR)
DATA_START = date(2025, 8, 1)                 # fixed 9-month window (stable data scale)
DATA_END = AS_OF_DATE                         # 2026-04-30
MONTH_START = AS_OF_DATE.replace(day=1)       # 2026-04-01
RECENT_START = add_months(MONTH_START, -2)    # 2026-02-01 (recent 3 full months incl. AS_OF month)

# ---------------------------------------------------------------- doctors
DOCTORS = [
    # (name, specialty, title, phone, hire_date, salary)
    ("王建国", "内科", "主任医师", "13800000001", date(2012, 3, 1), 28000.00),
    ("李秀兰", "外科", "副主任医师", "13800000002", date(2014, 7, 15), 25000.00),
    ("张伟", "皮肤科", "主治医师", "13800000003", date(2017, 2, 20), 18000.00),
    ("刘芳", "牙科", "主治医师", "13800000004", date(2018, 9, 10), 17000.00),
    ("陈强", "眼科", "副主任医师", "13800000005", date(2015, 5, 25), 22000.00),
    ("赵敏", "心脏科", "主任医师", "13800000006", date(2010, 11, 5), 32000.00),
    ("孙磊", "骨科", "主治医师", "13800000007", date(2019, 4, 18), 16000.00),
    ("周静", "营养科", "主治医师", "13800000008", date(2020, 1, 8), 15000.00),
]

# ---------------------------------------------------------------- owners
SURNAMES = "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾"
GIVEN_MALE = "伟强磊军洋勇杰涛明超平刚辉鹏飞凯毅建国志斌宇浩"
GIVEN_FEMALE = "芳娜敏静丽强萍红玲燕颖梅秀兰霞雪霞萍娟茜婷慧"
CITIES = ["上海", "北京", "杭州", "苏州", "南京", "宁波", "无锡"]


def _random_name():
    if random.random() < 0.5:
        return random.choice(SURNAMES) + random.choice(GIVEN_MALE) + random.choice(GIVEN_MALE)
    return random.choice(SURNAMES) + random.choice(GIVEN_FEMALE) + random.choice(GIVEN_FEMALE)


def gen_owners(count=30):
    owners = []
    used_phones = set()
    for i in range(count):
        phone = f"13{random.randint(100000000, 999999999)}"
        while phone in used_phones:
            phone = f"13{random.randint(100000000, 999999999)}"
        used_phones.add(phone)
        owners.append({
            "name": _random_name(),
            "phone": phone,
            "email": f"petowner{i + 1:02d}@example.com",
            "address": f"{random.choice(['阳光', '幸福', '锦绣', '金色', '紫荆', '梧桐'])}{random.choice(['小区', '花园', '苑', '城', '里'])}{random.randint(1, 120)}号",
            "city": random.choice(CITIES),
            "created_at": date(2024, random.randint(1, 12), random.randint(1, 28)),
        })
    return owners


# ---------------------------------------------------------------- pets
SPECIES_BREEDS = {
    "cat": ["英短蓝猫", "美短", "布偶", "暹罗", "橘猫", "中华田园猫", "英短银渐层"],
    "dog": ["金毛", "拉布拉多", "柯基", "贵宾", "比熊", "柴犬", "哈士奇", "泰迪", "中华田园犬", "博美"],
    "bird": ["虎皮鹦鹉", "玄凤鹦鹉", "牡丹鹦鹉", "文鸟"],
    "rabbit": ["垂耳兔", "侏儒兔", "安哥拉兔"],
    "hamster": ["金丝熊", "布丁仓鼠", "三线仓鼠"],
    "reptile": ["豹纹守宫", "鬃狮蜥", "玉米蛇"],
}
SPECIES_WEIGHT = {  # (min_kg, max_kg)
    "cat": (2.5, 8.0), "dog": (3.0, 40.0), "bird": (0.05, 0.5),
    "rabbit": (1.0, 3.0), "hamster": (0.02, 0.15), "reptile": (0.1, 0.8),
}


def gen_pets(owners, count=50):
    species_pool = ["cat"] * 20 + ["dog"] * 18 + ["rabbit"] * 4 + ["bird"] * 4 + ["hamster"] * 2 + ["reptile"] * 2
    random.shuffle(species_pool)
    pets = []
    for i in range(count):
        species = species_pool[i]
        lo, hi = SPECIES_WEIGHT[species]
        # birth_date uniformly in [2021-01-01, DATA_END]; never later than AS_OF_DATE
        earliest = date(2021, 1, 1)
        birth_date = earliest + timedelta(days=random.randint(0, (DATA_END - earliest).days))
        # created_at between birth_date and DATA_END (archive created after birth)
        created_at = birth_date + timedelta(days=random.randint(1, 120))
        if created_at > DATA_END:
            created_at = DATA_END
        pets.append({
            "owner_id": random.randint(1, len(owners)),
            "name": random.choice(["豆豆", "咪咪", "旺财", "团子", "布丁", "雪球", "可乐", "糯米", "奶茶", "元宝", "多多", "皮皮", "汤圆", "年糕", "胖虎", "花卷", "Lucky", "Momo", "Money", "小七"]),
            "species": species,
            "breed": random.choice(SPECIES_BREEDS[species]),
            "gender": "male" if random.random() < 0.5 else "female",
            "birth_date": birth_date,
            "weight": round(random.uniform(lo, hi), 2),
            "neutered": 1 if random.random() < 0.6 else 0,
            "created_at": created_at,
        })
    return pets


# ---------------------------------------------------------------- appointments
STATUS_POOL = ["completed"] * 70 + ["cancelled"] * 15 + ["no_show"] * 5 + ["booked"] * 10
REASONS = [
    "疫苗", "绝育手术", "皮肤病复诊", "肠胃不适", "体检", "驱虫", "牙科检查",
    "眼睛红肿", "咳嗽", "食欲不振", "骨折", "术后复查", "美容", "体重管理",
]


def gen_appointments(pets, doctors, start=None, end=None):
    start = start or DATA_START
    end = end or DATA_END
    # recent 3 months (RECENT_START ~ DATA_END) get ~35% density
    recent_start = RECENT_START
    aps = []
    cursor = start
    while cursor <= end:
        density = 0.9 if cursor >= recent_start else 0.5
        batch = random.randint(1, 3)
        for _ in range(batch):
            if random.random() > density:
                continue
            aps.append(_one_appointment(cursor, pets, doctors))
        cursor += timedelta(days=1)

    # deterministic-ish ordering: keep by date
    aps.sort(key=lambda a: (a["date"], a["time"]))
    return aps


def _one_appointment(day, pets, doctors, force_status=None, data_end=None):
    data_end = data_end or DATA_END
    status = force_status or random.choice(STATUS_POOL)
    if status == "booked" and day < data_end:
        status = random.choice(["completed", "completed", "cancelled"])  # no historical bookings
    reason = random.choice(REASONS)
    return {
        "pet_id": random.randint(1, len(pets)),
        "doctor_id": random.randint(1, len(doctors)),
        "date": day,
        "time": f"{random.randint(9, 17):02d}:{random.choice(['00', '15', '30', '45'])}:00",
        "reason": reason,
        "status": status,
    }


# ---------------------------------------------------------------- medical records
DIAGNOSIS_BY_SPECIALTY = {
    "内科": ["急性肠胃炎", "猫瘟(猫泛白细胞减少症)", "犬细小病毒感染", "慢性肾病", "胰腺炎", "甲状腺功能亢进"],
    "外科": ["前肢骨折", "膀胱结石", "胃内异物", "良性肿瘤切除", "剖腹产手术"],
    "皮肤科": ["皮肤真菌感染", "螨虫感染", "过敏性皮炎", "湿疹", "脓皮症"],
    "牙科": ["牙结石", "牙龈炎", "口腔溃疡", "牙周病", "牙齿松动"],
    "眼科": ["结膜炎", "白内障", "角膜溃疡", "青光眼", "第三眼睑增生"],
    "心脏科": ["扩张型心肌病", "充血性心力衰竭", "心包积液", "高血压", "心脏杂音"],
    "骨科": ["髋关节发育不良", "椎间盘突出", "前十字韧带断裂", "关节炎", "髌骨脱位"],
    "营养科": ["肥胖症", "营养不良", "糖尿病", "饮食过敏", "挑食厌食"],
}
TREATMENT_BY_SPECIALTY = {
    "内科": ["静脉补液+抗生素治疗", "支持疗法与营养管理", "消炎药口服+禁食观察", "激素治疗", "长期用药管理"],
    "外科": ["手术取出+术后护理", "骨折内固定手术", "伤口清创缝合", "肿瘤切除+病理送检", "术后抗生素治疗"],
    "皮肤科": ["抗真菌药浴+外用药", "驱螨治疗+环境消毒", "抗过敏药物+饮食调整", "药浴+口服消炎药", "激素软膏外用"],
    "牙科": ["超声波洁牙+抛光", "龈下刮治", "消炎药+口腔护理", "拔牙手术+止血", "牙周治疗+复查"],
    "眼科": ["抗生素眼药水+眼膏", "白内障手术评估", "角膜修复+消炎", "降眼压药物", "手术切除增生组织"],
    "心脏科": ["强心药物+利尿剂", "心衰长期管理", "心包穿刺引流", "降压药治疗", "心脏超声复查"],
    "骨科": ["保守治疗+限制运动", "关节营养补充剂", "十字韧带修复手术", "止痛+消炎治疗", "康复理疗"],
    "营养科": ["处方粮+体重管理计划", "营养补充剂", "胰岛素治疗+饮食控制", "食物回避试验", "分餐饲喂指导"],
}
MEDICINE_BY_SPECIALTY = {
    "内科": ["阿莫西林克拉维酸钾", "甲硝唑", "雷尼替丁", "多西环素", "益生菌制剂"],
    "外科": ["头孢氨苄", "美洛昔康", "云南白药", "阿莫西林", "布洛芬(犬用)"],
    "皮肤科": ["伊曲康唑", "特比萘芬", "泼尼松龙", "氯己定洗剂", "莫匹罗星软膏"],
    "牙科": ["甲硝唑漱口水", "阿莫西林", "氯己定凝胶", "布洛芬", "维生素B族"],
    "眼科": ["氧氟沙星滴眼液", "妥布霉素眼膏", "玻璃酸钠滴眼液", "乙酰唑胺", "红霉素眼膏"],
    "心脏科": ["匹莫苯丹", "呋塞米", "依那普利", "美托洛尔", "辅酶Q10"],
    "骨科": ["美洛昔康", "氨基葡萄糖", "杜仲壮骨片", "塞来昔布", "钙片"],
    "营养科": ["糖尿病处方粮", "皇家低脂粮", "营养膏", "鱼油胶囊", "复合维生素"],
}


def gen_medical_records(appointments, doctors, target=300):
    """One record per completed appointment (~95%), plus standalone emergency records."""
    completed = [a for a in appointments if a["status"] == "completed"]
    random.shuffle(completed)
    records = []
    for ap in completed[: int(len(completed) * 0.95)]:
        doctor = doctors[ap["doctor_id"] - 1]
        specialty = doctor["specialty"]
        records.append({
            "pet_id": ap["pet_id"],
            "doctor_id": ap["doctor_id"],
            "appointment_id": ap["appointment_id"],
            "record_date": ap["date"],
            "diagnosis": random.choice(DIAGNOSIS_BY_SPECIALTY[specialty]),
            "treatment": random.choice(TREATMENT_BY_SPECIALTY[specialty]),
            "medicine": random.choice(MEDICINE_BY_SPECIALTY[specialty]),
            "notes": random.choice(["两周后复诊", "注意饮食清淡", "按时用药,不适随诊", "避免剧烈运动", "多饮水观察", None, None, None]),
        })

    # standalone emergency records without appointment (recent weeks before DATA_END)
    emergency_days = [DATA_END - timedelta(days=d) for d in (45, 32, 25, 12, 5)]
    while len(records) < target and emergency_days:
        day = emergency_days.pop()
        doctor = random.choice(doctors)
        records.append({
            "pet_id": random.randint(1, 50),
            "doctor_id": doctor["doctor_id"],
            "appointment_id": None,
            "record_date": day,
            "diagnosis": random.choice(DIAGNOSIS_BY_SPECIALTY[doctor["specialty"]]),
            "treatment": "急诊处置+留院观察",
            "medicine": random.choice(MEDICINE_BY_SPECIALTY[doctor["specialty"]]),
            "notes": "急诊记录",
        })

    records.sort(key=lambda r: r["record_date"])
    return records[:target]


# ---------------------------------------------------------------- bills
BILL_PRICE = {
    "consultation": (50, 120),
    "examination": (80, 600),
    "surgery": (500, 3000),
    "medicine": (30, 300),
    "vaccine": (80, 200),
    "hospitalization": (150, 400),
    "grooming": (60, 200),
}
ITEM_DESC = {
    "consultation": ["普通门诊诊查费", "专家门诊诊查费", "急诊诊查费", "复诊诊查费"],
    "examination": ["血常规检查", "生化全套检查", "X光影像检查", "B超检查", "超声心动图", "皮肤刮片镜检", "粪便检查", "CT检查"],
    "surgery": ["绝育手术", "骨折内固定手术", "膀胱结石取出术", "肿瘤切除术", "剖腹产手术", "拔牙手术", "牙结石超声波洁治"],
    "medicine": ["抗生素注射", "消炎药", "止痛药", "止吐药", "皮肤外用药", "驱虫药", "营养补充剂"],
    "vaccine": ["猫三联疫苗", "犬四联疫苗", "狂犬疫苗", "猫瘟抗体检测+疫苗", "犬窝咳疫苗"],
    "hospitalization": ["住院护理费(按天)", "输液治疗费(按天)", "重症监护费(按天)"],
    "grooming": ["猫咪洗护美容", "狗狗洗护美容", "宠物剪毛造型", "宠物SPA护理"],
}
PAY_STATUS_POOL = ["paid"] * 88 + ["unpaid"] * 7 + ["refunded"] * 5
PAY_METHOD_POOL = ["wechat", "alipay", "card", "cash"]


def _bill_amount(item_type, record):
    lo, hi = BILL_PRICE[item_type]
    if item_type == "hospitalization":
        days = random.randint(1, 5)
        return round(random.uniform(lo, hi) * days, 2)
    if item_type == "surgery" and record is not None and "骨折" in record["diagnosis"]:
        return round(random.uniform(1500, 3000), 2)
    if item_type == "examination" and record is not None and "心脏" in record["diagnosis"]:
        return round(random.uniform(300, 600), 2)
    return round(random.uniform(lo, hi), 2)


def gen_bills(records, appointments, pets, target=500):
    bills = []
    billed_days = {}
    for record in records:
        rid = record["record_id"]
        # core consultation + 1-3 extra items
        items = ["consultation"]
        extras = random.choices(["examination", "medicine", "surgery", "hospitalization", "medicine", "examination"], k=random.randint(1, 3))
        items.extend(extras[:random.randint(1, 2)])
        bill_date = record["record_date"] + timedelta(days=random.choice([0, 0, 1, 2]))
        if bill_date > DATA_END:
            bill_date = DATA_END  # clamp to data end
        for it in items:
            pay_status = random.choice(PAY_STATUS_POOL)
            if pay_status == "unpaid" and bill_date < RECENT_START:
                pay_status = "paid"  # unpaid only makes sense recently
            bills.append({
                "pet_id": record["pet_id"],
                "doctor_id": record["doctor_id"],
                "record_id": rid,
                "item_type": it,
                "item_desc": random.choice(ITEM_DESC[it]),
                "amount": _bill_amount(it, record),
                "billed_date": bill_date,
                "pay_status": pay_status,
                "payment_method": random.choice(PAY_METHOD_POOL) if pay_status == "paid" else None,
            })

    # standalone bills: vaccines & grooming for some pets (no record link)
    window = (DATA_END - RECENT_START).days
    pet_ids = list(range(1, len(pets) + 1))
    random.shuffle(pet_ids)
    for i, pet_id in enumerate(pet_ids[:28]):
        if i % 2 == 0:  # vaccination course
            for v in range(random.randint(1, 2)):
                d = RECENT_START + timedelta(days=random.randint(0, window))
                bills.append({
                    "pet_id": pet_id,
                    "doctor_id": random.randint(1, 8),
                    "record_id": None,
                    "item_type": "vaccine",
                    "item_desc": random.choice(ITEM_DESC["vaccine"]),
                    "amount": round(random.uniform(*BILL_PRICE["vaccine"]), 2),
                    "billed_date": d,
                    "pay_status": random.choice(["paid", "paid", "paid", "unpaid"]),
                    "payment_method": random.choice(PAY_METHOD_POOL),
                })
        else:  # grooming
            d = RECENT_START + timedelta(days=random.randint(0, window))
            bills.append({
                "pet_id": pet_id,
                "doctor_id": random.randint(1, 8),
                "record_id": None,
                "item_type": "grooming",
                "item_desc": random.choice(ITEM_DESC["grooming"]),
                "amount": round(random.uniform(*BILL_PRICE["grooming"]), 2),
                "billed_date": d,
                "pay_status": "paid",
                "payment_method": random.choice(PAY_METHOD_POOL),
            })

    bills.sort(key=lambda b: b["billed_date"])
    return bills[-target:]  # keep the most recent `target` bills


# ---------------------------------------------------------------- SQL writer
def _fmt_date(d):
    return d.isoformat()


def _null(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return _esc(v)


def _esc(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def main():
    owners = gen_owners(30)
    pets = gen_pets(owners, 50)
    doctors = [
        {"doctor_id": i + 1, "name": d[0], "specialty": d[1], "title": d[2], "phone": d[3], "hire_date": d[4], "salary": d[5]}
        for i, d in enumerate(DOCTORS)
    ]
    appointments = gen_appointments(pets, doctors)
    for i, ap in enumerate(appointments):
        ap["appointment_id"] = i + 1
    records = gen_medical_records(appointments, doctors, target=300)
    for i, r in enumerate(records):
        r["record_id"] = i + 1
    bills = gen_bills(records, appointments, pets, target=500)
    for i, b in enumerate(bills):
        b["bill_id"] = i + 1

    out = []
    out.append("-- PetCare seed data (generated by gen_seed.py, deterministic seed=42)")
    out.append("USE petcare_db;")
    out.append("SET FOREIGN_KEY_CHECKS = 0;")
    out.append("TRUNCATE TABLE bills; TRUNCATE TABLE medical_records; TRUNCATE TABLE appointments; TRUNCATE TABLE pets; TRUNCATE TABLE doctors; TRUNCATE TABLE owners;")
    out.append("SET FOREIGN_KEY_CHECKS = 1;")

    out.append("INSERT INTO owners (owner_id, name, phone, email, address, city, created_at) VALUES")
    out.append(",\n".join(
        f"({o['owner_id'] if 'owner_id' in o else i + 1}, {_esc(o['name'])}, {_esc(o['phone'])}, {_esc(o['email'])}, {_esc(o['address'])}, {_esc(o['city'])}, {_esc(o['created_at'])})"
        for i, o in enumerate(owners)) + ";")

    out.append("INSERT INTO doctors (doctor_id, name, specialty, title, phone, hire_date, salary, status) VALUES")
    out.append(",\n".join(
        f"({d['doctor_id']}, {_esc(d['name'])}, {_esc(d['specialty'])}, {_esc(d['title'])}, {_esc(d['phone'])}, {_esc(d['hire_date'])}, {d['salary']}, 'active')"
        for d in doctors) + ";")

    out.append("INSERT INTO pets (pet_id, owner_id, name, species, breed, gender, birth_date, weight, neutered, created_at) VALUES")
    out.append(",\n".join(
        f"({i + 1}, {p['owner_id']}, {_esc(p['name'])}, {_esc(p['species'])}, {_esc(p['breed'])}, {_esc(p['gender'])}, {_esc(p['birth_date'])}, {p['weight']}, {p['neutered']}, {_esc(p['created_at'])})"
        for i, p in enumerate(pets)) + ";")

    out.append("INSERT INTO appointments (appointment_id, pet_id, doctor_id, appointment_date, appointment_time, reason, status) VALUES")
    out.append(",\n".join(
        f"({a['appointment_id']}, {a['pet_id']}, {a['doctor_id']}, {_esc(a['date'])}, {_esc(a['time'])}, {_esc(a['reason'])}, {_esc(a['status'])})"
        for a in appointments) + ";")

    out.append("INSERT INTO medical_records (record_id, pet_id, doctor_id, appointment_id, record_date, diagnosis, treatment, medicine, notes) VALUES")
    out.append(",\n".join(
        f"({r['record_id']}, {r['pet_id']}, {r['doctor_id']}, {_null(r['appointment_id'])}, {_esc(r['record_date'])}, {_esc(r['diagnosis'])}, {_esc(r['treatment'])}, {_esc(r['medicine'])}, {_esc(r['notes'])})"
        for r in records) + ";")

    out.append("INSERT INTO bills (bill_id, pet_id, doctor_id, record_id, item_type, item_desc, amount, billed_date, pay_status, payment_method) VALUES")
    out.append(",\n".join(
        f"({b['bill_id']}, {b['pet_id']}, {b['doctor_id']}, {_null(b['record_id'])}, {_esc(b['item_type'])}, {_esc(b['item_desc'])}, {b['amount']}, {_esc(b['billed_date'])}, {_esc(b['pay_status'])}, {_null(b['payment_method'])})"
        for b in bills) + ";")

    with open("seed.sql", "w", encoding="utf-8") as f:
        f.write("\n\n".join(out) + "\n")

    # stats
    print(f"owners={len(owners)} pets={len(pets)} doctors={len(doctors)}")
    print(f"appointments={len(appointments)} records={len(records)} bills={len(bills)}")
    from collections import Counter
    print("appointment status:", dict(Counter(a["status"] for a in appointments)))
    print("bill pay_status:", dict(Counter(b["pay_status"] for b in bills)))
    print("bill item_type:", dict(Counter(b["item_type"] for b in bills)))
    recent = [b for b in bills if b["billed_date"] >= RECENT_START]
    print(f"bills in recent 3 months ({RECENT_START}~{DATA_END}): {len(recent)}")
    print(f"window: {DATA_START} ~ {DATA_END} (AS_OF_DATE={AS_OF_DATE})")


if __name__ == "__main__":
    main()
