import re

W = [
    "صفر", "ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو",
    "دس", "گیارہ", "بارہ", "تیرہ", "چودہ", "پندرہ", "سولہ", "سترہ", "اٹھارہ", "انیس",
    "بیس", "اکیس", "بائیس", "تئیس", "چوبیس", "پچیس", "چھبیس", "ستائیس", "اٹھائیس", "انتیس",
    "تیس", "اکتیس", "بتیس", "تینتیس", "چونتیس", "پینتیس", "چھتیس", "سینتیس", "اڑتیس", "انتالیس",
    "چالیس", "اکتالیس", "بیالیس", "تینتالیس", "چوالیس", "پینتالیس", "چھیالیس", "سینتالیس", "اڑتالیس", "انچاس",
    "پچاس", "اکیاون", "باون", "ترپن", "چون", "پچپن", "چھپن", "ستاون", "اٹھاون", "انسٹھ",
    "ساٹھ", "اکسٹھ", "باسٹھ", "تریسٹھ", "چونسٹھ", "پینسٹھ", "چھیاسٹھ", "سڑسٹھ", "اڑسٹھ", "انہتر",
    "ستر", "اکہتر", "بہتر", "تہتر", "چوہتر", "پچھتر", "چھہتر", "ستتر", "اٹھہتر", "اناسی",
    "اسی", "اکاسی", "بیاسی", "تراسی", "چوراسی", "پچاسی", "چھیاسی", "ستاسی", "اٹھاسی", "نواسی",
    "نوے", "اکانوے", "بانوے", "ترانوے", "چورانوے", "پچانوے", "چھیانوے", "ستانوے", "اٹھانوے", "ننانوے",
]


def num_to_urdu(n):
    if n < 100:
        return W[n]
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1_000)
    hundred, n = divmod(n, 100)
    parts = []
    if crore:
        parts.append(num_to_urdu(crore) + " کروڑ")
    if lakh:
        parts.append(W[lakh] + " لاکھ")
    if thousand:
        parts.append(W[thousand] + " ہزار")
    if hundred:
        parts.append(W[hundred] + " سو")
    if n:
        parts.append(W[n])
    return " ".join(parts)


def _digits_one_by_one(s):
    return " ".join(W[int(d)] for d in s if d.isdigit())


def for_speech(text):
    text = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    text = re.sub(r"(?<=\d),(?=\d)", "", text)           # Pakistani style: 1,25,000
    text = re.sub(r"\b0\d{3}-?\d{7}\b", lambda m: _digits_one_by_one(m.group()), text)

    def _time(m):
        h, mins = int(m.group(1)), int(m.group(2))
        return f"{W[h]} بجے" if mins == 0 else f"{W[h]} بج کر {W[mins]} منٹ"
    text = re.sub(r"\b(\d{1,2}):(\d{2})\b", _time, text)

    text = re.sub(r"(?:Rs\.?|PKR)\s*(\d+)", lambda m: f"{num_to_urdu(int(m.group(1)))} روپے", text)
    text = re.sub(r"\d+", lambda m: num_to_urdu(int(m.group())) if len(m.group()) <= 9
                  else _digits_one_by_one(m.group()), text)
    return text


if __name__ == "__main__":
    for t in ["آپ کے آرڈر کی رقم 4,500 روپے ہے",
              "ڈلیوری چارجز Rs. 250 ہیں، اور Rs 5,000 سے زیادہ پر مفت",
              "فارمل سوٹ 15500 روپے کا ہے",
              "24 گھنٹے بعد آرڈر کینسل ہو جائے گا",
              "واٹس ایپ نمبر 0300-0000000 ہے",
              "رات 11:35 پر",
              "قیمت 1,25,000 روپے"]:
        print(t, "\n   ->", for_speech(t), "\n")