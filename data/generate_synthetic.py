import csv
import random
from datetime import datetime, timedelta
from collections import Counter

random.seed(42)

FIRST_NAMES = [
    "Maria","Sarah","Angela","Dawn","Shelly","Lorraine","Theresa","Jolene",
    "Nizhoni","Shima","Yanaba","Sandra","Carol","Patricia","Tanya","Ruth",
    "James","Robert","David","Marcus","Leonard","Thomas","Tohono","Sani",
    "Bidziil","Harold","Eugene","Chester","Lloyd","Raymond","Gordon","Calvin",
    "Herman","Alvin","Dibe","Naat"
]
LAST_NAMES = [
    "Runningwater","Cloudwalker","Redhouse","Silversmith","Begay","Yazzie",
    "Nez","Tsosie","Benally","Bitsuie","Fowler","Tallman","Blackhorse",
    "Whiterock","Hatathlie","Greyhorse","Draper","Ethelbah","Goldtooth","Cly"
]
CERTIFICATE_PROGRAMS = [
    "Early Childhood Education","Administrative Office Technology",
    "Redrock Language and Culture","Environmental Science Technology",
    "Nursing Assistant"
]
ASSOCIATES_PROGRAMS = [
    "Business Administration","Liberal Arts","Science","Education","Natural Resources"
]
BACHELORS_PROGRAMS = [
    "Elementary Education","Business Administration","Redrock Studies"
]
DATE_FORMATS = ["%Y-%m-%d","%m/%d/%Y","%d-%b-%Y"]

def random_date():
    base = datetime.today()
    delta = random.randint(7,300)
    d = base - timedelta(days=delta)
    return d.strftime(random.choice(DATE_FORMATS))

used_ids = set()
def new_id():
    while True:
        i = str(random.randint(10001,10999))
        if i not in used_ids:
            used_ids.add(i)
            return i

used_names = set()
def new_name():
    for _ in range(200):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        if (first,last) not in used_names:
            used_names.add((first,last))
            return first,last
    raise ValueError("Name pool exhausted")

def make_row(
    stu_id, first, last,
    program_type, program_name,
    credits_earned, current_credits,
    next_term_registered, last_contact,
    enrollment_status, reg_hold,
    stop_out_terms, transfer_credits,
    _profile, _expected_flag,
    blank_credits=False,
    bool_format="true_false",
    blank_registered=False,
):
    def fmt_bool(val):
        if val is None: return ""
        if bool_format == "y_n": return "Y" if val else "N"
        return "True" if val else "False"
    return {
        "stu_id": stu_id,
        "first_name": first,
        "last_name": last,
        "program_type": program_type,
        "program_name": program_name,
        "credits_earned": "" if blank_credits else credits_earned,
        "current_credits": current_credits,
        "next_term_registered": "" if blank_registered else fmt_bool(next_term_registered),
        "last_contact": last_contact,
        "enrollment_status": enrollment_status,
        "reg_hold": fmt_bool(reg_hold),
        "stop_out_terms": stop_out_terms,
        "transfer_credits": transfer_credits,
        "_profile": _profile,
        "_expected_flag": _expected_flag,
    }

rows = []

# ── PROFILE A: Classic momentum — Associate\'s (3 records) ────────────────────
# credits >= 12, not registered, no hold, no stop-out
# remaining = 60 - credits - in_progress >> 3 so OCA won\'t fire
for credits in [24, 30, 36]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"associates",random.choice(ASSOCIATES_PROGRAMS),
        credits,3,False,random_date(),"active",False,"",0,
        "A_momentum_associates","momentum_nudge_deterministic"
    ))

# ── PROFILE B: Certificate mid-way (3 records) ───────────────────────────────
# credits >= 12, not registered, remaining = 30 - credits - 3 >> 3
for credits in [15, 18, 21]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"certificate",
        random.choice(["Early Childhood Education","Administrative Office Technology"]),
        credits,3,False,random_date(),"active",False,"",0,
        "B_momentum_certificate","momentum_nudge_deterministic"
    ))

# ── PROFILE C: Part-time bachelor\'s (2 records) ──────────────────────────────
# credits >= 12, not registered, remaining = 120 - credits - 6 >> 3
for credits in [48, 56]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"bachelors",random.choice(BACHELORS_PROGRAMS),
        credits,6,False,random_date(),"active",False,"",0,
        "C_momentum_bachelors","momentum_nudge_deterministic"
    ))

# ── PROFILE D: Certificate completion (3 records) ────────────────────────────
# remaining = 30 - credits - 0 = 2 or 3, no transfer credits
for credits in [27, 27, 28]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"certificate",random.choice(CERTIFICATE_PROGRAMS),
        credits,0,False,random_date(),"active",False,"",0,
        "D_one_course_certificate","one_course_away_deterministic"
    ))

# ── PROFILE E: Associate\'s completion (3 records) ────────────────────────────
# remaining = 60 - credits - 0 = 2 or 3, no transfer credits
for credits in [57, 58, 58]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"associates",random.choice(ASSOCIATES_PROGRAMS),
        credits,0,False,random_date(),"active",False,"",0,
        "E_one_course_associates","one_course_away_deterministic"
    ))

# ── PROFILE F: Seasonal stop-out (2 records) ─────────────────────────────────
# credits >= 12, stop-out same term in prior years -> ambiguous
for credits,stop in [(23,"Spring 2024|Spring 2023"),(19,"Spring 2024|Spring 2022")]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"associates",random.choice(ASSOCIATES_PROGRAMS),
        credits,3,False,random_date(),"active",False,stop,0,
        "F_seasonal_stopout","momentum_nudge_llm"
    ))

# ── PROFILE G: Just below threshold (2 records) ──────────────────────────────
# credits < 12 but credits + in_progress >= 12 -> ambiguous
# 11 + 3 = 14 >= 12, 10 + 3 = 13 >= 12
for credits in [11, 10]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"certificate",random.choice(CERTIFICATE_PROGRAMS),
        credits,3,False,random_date(),"active",False,"",0,
        "G_below_threshold","momentum_nudge_llm"
    ))

# ── PROFILE H: Unknown hold status (1 record) ────────────────────────────────
# reg_hold = None -> ambiguous
f,l = new_name()
rows.append(make_row(
    new_id(),f,l,"associates",random.choice(ASSOCIATES_PROGRAMS),
    30,3,False,random_date(),"active",None,"",0,
    "H_unknown_hold","momentum_nudge_llm"
))

# ── PROFILE I: Pending transfer credits (2 records) ──────────────────────────
# remaining = 60 - credits = 6 or 4, transfer credits could close gap
for credits,transfer in [(54,9),(56,6)]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"associates",random.choice(ASSOCIATES_PROGRAMS),
        credits,0,False,random_date(),"active",False,"",transfer,
        "I_transfer_pending","one_course_away_llm"
    ))

# ── PROFILE J: Dual milestone (1 record) ─────────────────────────────────────
# associates remaining = 60 - 57 - 0 = 3, transfer_credits = 27
# Routes to ambiguous via the transfer-pending check (remaining <= transfer + 3),
# not a dedicated dual-milestone rule — see rules.py / check_one_course_away.
f,l = new_name()
rows.append(make_row(
    new_id(),f,l,"associates","Science",
    57,0,False,random_date(),"active",False,"",27,
    "J_dual_milestone","one_course_away_llm"
))

# ── PROFILE K: Already eligible, hasn\'t applied (1 record) ───────────────────
# remaining = 30 - 30 - 0 = 0 -> ambiguous (already eligible)
f,l = new_name()
rows.append(make_row(
    new_id(),f,l,"certificate","Nursing Assistant",
    30,0,False,random_date(),"active",False,"",0,
    "K_already_eligible","one_course_away_llm"
))

# ── PROFILE L: Missing credits (4 records) ───────────────────────────────────
for _ in range(4):
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"associates",random.choice(ASSOCIATES_PROGRAMS),
        0,0,False,random_date(),"active",False,"",0,
        "L_missing_credits","human_review_data_quality",
        blank_credits=True
    ))

# ── PROFILE M: Inactive (3 records) ──────────────────────────────────────────
for credits in [12, 9, 13]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,random.choice(["certificate","associates"]),
        random.choice(ASSOCIATES_PROGRAMS),
        credits,0,False,random_date(),"inactive",False,
        random.choice(["Fall 2023","Spring 2024",""]),0,
        "M_inactive","no_flag"
    ))

# ── PROFILE N: Registration hold (2 records) ─────────────────────────────────
# hold = True -> momentum suppressed even though credits >= 12
for credits in [23, 26]:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,"associates",random.choice(ASSOCIATES_PROGRAMS),
        credits,3,False,random_date(),"active",True,"",0,
        "N_registration_hold","no_flag_hold"
    ))

# ── PROFILE O: Duplicate record (1 pair) ─────────────────────────────────────
dup_id = new_id()
f,l = new_name()
rows.append(make_row(
    dup_id,f,l,"associates","Liberal Arts",
    18,0,False,random_date(),"active",False,"",0,
    "O_duplicate_lower","deduplication_discard"
))
rows.append(make_row(
    dup_id,f,l,"associates","Liberal Arts",
    24,3,False,random_date(),"active",False,"",0,
    "O_duplicate_higher","momentum_nudge_deterministic"
))

# ── CLEAN RECORDS: 42 no-flag students ───────────────────────────────────────
# Rule: if registered=True, any credits are safe (rules exit immediately)
#       if registered=False, credits MUST be < 12 AND credits+in_progress < 12
#       so neither momentum nor OCA can fire
clean_records = [
    # registered=True — safe at any credit level
    ("associates",   22, 3, True,  0,  ""),
    ("associates",   15, 3, True,  0,  ""),
    ("certificate",  12, 3, True,  0,  ""),
    ("associates",   24, 3, True,  0,  ""),
    ("bachelors",    40, 6, True,  0,  ""),
    ("associates",   18, 3, True,  0,  ""),
    ("certificate",   9, 3, True,  0,  ""),
    ("associates",   39, 3, True,  0,  ""),
    ("associates",   48, 3, True,  0,  ""),
    ("bachelors",    48, 6, True,  0,  ""),
    ("associates",   42, 3, True,  0,  ""),
    ("associates",   23, 3, True,  6,  ""),
    ("certificate",  19, 3, True,  0,  ""),
    ("associates",   13, 3, True,  3,  ""),
    ("associates",   22, 3, True,  3,  ""),
    ("bachelors",    50, 6, True,  3,  ""),
    ("associates",   42, 6, True,  6,  ""),
    ("associates",   26, 3, True,  6,  ""),
    ("certificate",   8, 3, True,  0,  ""),
    ("associates",   53, 6, True,  6,  ""),
    ("bachelors",    60, 0, True,  0,  ""),
    ("associates",   50, 3, True,  3,  ""),
    # registered=False — credits < 12 AND credits+in_progress < 12
    ("certificate",   7, 0, False, 0,  ""),
    ("certificate",   6, 0, False, 0,  ""),
    ("associates",    8, 0, False, 0,  ""),
    ("associates",    9, 0, False, 0,  ""),
    ("certificate",   5, 0, False, 0,  ""),
    ("associates",    6, 0, False, 0,  ""),
    ("associates",    7, 0, False, 0,  ""),
    ("associates",    4, 0, False, 0,  ""),
    ("associates",    8, 0, False, 0,  ""),
    ("associates",    9, 0, False, 0,  ""),
    ("certificate",   6, 0, False, 0,  ""),
    ("associates",    7, 0, False, 0,  ""),
    ("associates",    5, 0, False, 0,  ""),
    ("bachelors",     8, 0, False, 0,  ""),
    ("bachelors",     9, 0, False, 0,  ""),
    ("associates",    6, 0, False, 0,  ""),
    ("associates",    7, 0, False, 0,  ""),
    ("associates",    9, 0, False, 0,  ""),
    ("associates",    8, 0, False, 0,  ""),
    ("associates",   11, 0, False, 0,  ""),
]

for pt,ce,cc,reg,tc,stop in clean_records:
    f,l = new_name()
    rows.append(make_row(
        new_id(),f,l,pt,
        random.choice(
            CERTIFICATE_PROGRAMS if pt=="certificate"
            else BACHELORS_PROGRAMS if pt=="bachelors"
            else ASSOCIATES_PROGRAMS
        ),
        ce,cc,reg,random_date(),"active",False,stop,tc,
        "clean_no_flag","no_flag"
    ))

# ── Apply Data Quality Issues ─────────────────────────────────────────────────
# 1. Mixed Y/N boolean — 5 records from registered=True clean students
yn_pool = [i for i,r in enumerate(rows)
           if r["_expected_flag"]=="no_flag"
           and r["next_term_registered"]=="True"]
yn_indices = random.sample(yn_pool, 5)
for i in yn_indices:
    rows[i]["next_term_registered"] = "Y"

# 2. Null next_term_registered — 3 records from registered=True clean students
null_pool = [i for i,r in enumerate(rows)
             if r["_expected_flag"]=="no_flag"
             and r["next_term_registered"] in ("True","Y")]
null_indices = random.sample(null_pool, 3)
for i in null_indices:
    rows[i]["next_term_registered"] = ""

# 3. Unrecognized program_type — 2 records from clean students
legacy_pool = [i for i,r in enumerate(rows) if r["_expected_flag"]=="no_flag"]
legacy_indices = random.sample(legacy_pool, 2)
for i,code in zip(legacy_indices,["CERT-ECE","AS-BUS"]):
    rows[i]["program_type"] = code

# 4. Encoding artifact — 1 record
enc_pool = [i for i,r in enumerate(rows) if r["_expected_flag"]=="no_flag"]
enc_index = random.choice(enc_pool)
rows[enc_index]["last_name"] = rows[enc_index]["last_name"] + "e\\u0301"

# ── Shuffle and Write ─────────────────────────────────────────────────────────
random.shuffle(rows)

output_path = "data/synthetic/redrock_students.csv"
fieldnames = [
    "stu_id","first_name","last_name","program_type","program_name",
    "credits_earned","current_credits","next_term_registered",
    "last_contact","enrollment_status","reg_hold","stop_out_terms",
    "transfer_credits","_profile","_expected_flag",
]
with open(output_path,"w",newline="",encoding="utf-8") as f:
    writer = csv.DictWriter(f,fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows to {output_path}")
flags = Counter(r["_expected_flag"] for r in rows)
print("\\nFlag distribution:")
for flag,count in sorted(flags.items()):
    print(f"  {flag:40} {count}")
