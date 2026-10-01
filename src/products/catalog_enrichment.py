import re
from collections import OrderedDict

from django.db import transaction
from django.utils.text import slugify
from unidecode import unidecode

from products.models import Attribute, AttributeValue, CategoryAttribute


ATTRIBUTE_ORDER = {
    "Тип товара": 1,
    "Единица продажи": 2,
    "Цвет": 10,
    "Размер": 20,
    "Диаметр колеса": 30,
    "Длина": 40,
    "Сторона привода": 50,
    "Количество отверстий": 60,
    "Материал": 70,
}


def taobao_item_id(external_id: str) -> str:
    """Return the parent Taobao item id, shared by all of its SKUs."""
    return (external_id or "").split(":sku:", 1)[0].strip()


def _first(pattern, text, flags=re.I):
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""


def extract_characteristics(*parts: str) -> dict[str, str]:
    """Extract conservative, customer-facing bicycle specs from imported text."""
    text = " ".join(str(part or "") for part in parts)
    compact = re.sub(r"\s+", " ", text).strip()
    lower = compact.lower().replace(",", ".")
    values = OrderedDict()

    if "左驱" in compact or re.search(r"\b(?:лев(?:ый|ого)|left)\s*(?:привод)?\b", lower):
        values["Сторона привода"] = "Левая"
    elif "右驱" in compact or re.search(r"\b(?:прав(?:ый|ого)|right)\s*(?:привод)?\b", lower):
        values["Сторона привода"] = "Правая"

    color_rules = (
        (r"(?:黑色?|ч[её]рн(?:ый|ая|ое)|\bblack\b|flat black)", "Чёрный"),
        (r"(?:白色?|бел(?:ый|ая|ое)|\bwhite\b)", "Белый"),
        (r"(?:银色?|серебр(?:о|истый|яный)|\bsilver\b)", "Серебристый"),
        (r"(?:红色?|красн(?:ый|ая|ое)|\bred\b)", "Красный"),
        (r"(?:蓝色?|син(?:ий|яя|ее)|\bblue\b)", "Синий"),
        (r"(?:绿色?|зел[её]н(?:ый|ая|ое)|\bgreen\b)", "Зелёный"),
        (r"(?:紫色?|фиолетов(?:ый|ая|ое)|\bpurple\b)", "Фиолетовый"),
        (r"(?:金色?|золот(?:ой|ая|ое)|\bgold\b)", "Золотой"),
        (r"(?:钛本色|титанов(?:ый цвет|ого цвета)|titanium)", "Титановый"),
        (r"(?:电镀|гальваническ(?:ое|ий) покрытие|\bchrome\b|хром)", "Хром"),
    )
    for pattern, label in color_rules:
        if re.search(pattern, lower, re.I):
            values["Цвет"] = label
            break

    material_rules = (
        (r"(?:钛合金|титанов(?:ый|ая|ое)(?:\s+сплав)?|\btitanium\b)", "Титановый сплав"),
        (r"(?:碳纤维|карбон|углеволок|\bcarbon\b)", "Карбон"),
        (r"(?:铝合金|алюминиев|\baluminium\b|\baluminum\b)", "Алюминиевый сплав"),
        (r"(?:хромомолибден|cr-?mo|4130)", "Хромомолибденовая сталь"),
        (r"(?:кевлар|\bkevlar\b)", "Кевлар"),
    )
    for pattern, label in material_rules:
        if re.search(pattern, lower, re.I):
            values["Материал"] = label
            break

    holes = _first(r"(\d{2})\s*(?:孔|отверст)", lower)
    if holes:
        values["Количество отверстий"] = holes

    top_tube = _first(r"(?:上管|top\s*tube|верхн\w*\s+труб\w*)\s*[:：]?\s*(\d{2}(?:\.\d{1,2})?)", lower)
    if top_tube:
        values["Размер"] = f'{top_tube}"'

    mm = _first(r"(?<!\d)(\d{2,3}(?:\.\d+)?)\s*mm\b", lower)
    if mm:
        values.setdefault("Длина", f"{mm} мм")

    wheel = _first(r"(?<!\d)(1[2468]|20|24|26|27\.5|29)\s*(?:寸|дюйм|\")", lower)
    if wheel:
        values["Диаметр колеса"] = f'{wheel}"'

    inch_size = _first(r"(?:颜色分类|商品规格|规格)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*寸", lower)
    if inch_size and "Диаметр колеса" not in values:
        values["Размер"] = f'{inch_size}"'

    generic_size = _first(r"(?:商品规格|规格|размер|size)\s*[:：]?\s*([a-z0-9][a-z0-9 .x/\-\"]{0,30})", lower)
    if generic_size:
        generic_size = re.split(r"(?:цвет|颜色|категор|бренд|вариант)", generic_size)[0].strip(" .,-")
        if generic_size:
            values.setdefault("Размер", generic_size.upper() if generic_size in {"xs", "s", "m", "l", "xl", "xxl"} else generic_size)

    return dict(values)


def extract_description_characteristics(description: str) -> dict[str, str]:
    """Read the human-written ``Характеристики`` block without losing units."""
    text = str(description or "").replace("\r", "")
    marker = re.search(r"(?:^|\n)\s*характеристики\s*:?\s*(?:\n|$)", text, re.I)
    if not marker:
        return {}

    values = OrderedDict()
    for raw_line in text[marker.end():].splitlines():
        line = re.sub(r"^[\s•·*–—-]+", "", raw_line).strip()
        if not line:
            continue
        match = re.match(r"([^:–—-]{2,80}?)\s*(?:[:–—-])\s*(.+)$", line)
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        value = re.sub(r"\s+", " ", match.group(2)).strip(" .")
        if name and value:
            values[name[:120]] = value[:255]
    return dict(values)


@transaction.atomic
def apply_characteristics(product, variant, values: dict[str, str], *, variant_names=()):
    """Persist extracted specs and configure category filters/variant selectors."""
    for name, value in values.items():
        attribute, _ = Attribute.objects.get_or_create(
            name=name,
            defaults={"slug": slugify(unidecode(name)), "value_type": Attribute.TEXT},
        )
        is_variant = name in set(variant_names)
        usage, _ = CategoryAttribute.objects.get_or_create(
            category=product.category,
            attribute=attribute,
            defaults={
                "is_filterable": True,
                "is_variant": is_variant,
                "sort_order": ATTRIBUTE_ORDER.get(name, 100),
            },
        )
        if is_variant and not usage.is_variant:
            usage.is_variant = True
            usage.save(update_fields=["is_variant"])
        owner = {"variant": variant} if is_variant else {"product": product}
        AttributeValue.objects.update_or_create(
            attribute=attribute,
            **owner,
            defaults={"value_text": value, "value_number": None, "value_bool": None},
        )
