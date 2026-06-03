from dataclasses import dataclass, field
import openpyxl

TEMPLATE_COLUMNS = ["품번", "상품명", "색상", "사이즈", "도매가", "판매가"]
_KEY = {"품번": "source_p_number", "상품명": "item_name", "색상": "color",
        "사이즈": "size", "도매가": "wholesale_price", "판매가": "retail_price"}


@dataclass
class ParseResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


def parse_template_rows(path: str) -> ParseResult:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    res = ParseResult()
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        rec = {_KEY[c]: (row[j] if j < len(row) else None) for j, c in enumerate(TEMPLATE_COLUMNS)}
        try:
            rec["wholesale_price"] = int(rec["wholesale_price"])
            rec["retail_price"] = int(rec["retail_price"]) if rec["retail_price"] not in (None, "") else None
            if not rec["source_p_number"] or not rec["item_name"]:
                raise ValueError("필수값 누락")
            res.rows.append(rec)
        except (TypeError, ValueError) as e:
            res.errors.append({"row": i, "reason": str(e), "raw": list(row)})
    return res
