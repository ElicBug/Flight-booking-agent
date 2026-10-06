"""Generate the Vietnamese agent evaluation PDF from recorded JSONL runs."""

from __future__ import annotations

import json
from pathlib import Path
import statistics

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
OUTPUT = ROOT / "reports" / "agent_evaluation.pdf"
FONT_DIR = Path("C:/Windows/Fonts")
GITHUB_URL = "https://github.com/ElicBug/Flight-booking-agent"

INK = colors.HexColor("#172A3A")
TEAL = colors.HexColor("#0E7775")
PALE = colors.HexColor("#EAF3F2")
LIGHT = colors.HexColor("#F4F6F7")
MUTED = colors.HexColor("#526372")
WHITE = colors.white


def register_vietnamese_fonts() -> None:
    regular_path = FONT_DIR / "arial.ttf"
    bold_path = FONT_DIR / "arialbd.ttf"
    if not regular_path.exists() or not bold_path.exists():
        raise FileNotFoundError("Cần font Arial hỗ trợ tiếng Việt trong C:/Windows/Fonts.")
    pdfmetrics.registerFont(TTFont("ReportArial", str(regular_path)))
    pdfmetrics.registerFont(TTFont("ReportArial-Bold", str(bold_path)))
    pdfmetrics.registerFontFamily(
        "ReportArial",
        normal="ReportArial",
        bold="ReportArial-Bold",
        italic="ReportArial",
        boldItalic="ReportArial-Bold",
    )


def read_runs(name: str) -> list[dict[str, object]]:
    path = RUNS_DIR / f"{name}.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def mean(records: list[dict[str, object]], key: str, digits: int = 3) -> str:
    values = [float(record[key]) for record in records if record.get(key) is not None]
    if not values:
        return "Chưa có dữ liệu"
    average = statistics.mean(values)
    if digits == 0:
        return f"{average:,.0f}".replace(",", ".")
    return f"{average:.{digits}f}".replace(".", ",")


def success_ratio(records: list[dict[str, object]]) -> str:
    if not records:
        return "Chưa có dữ liệu"
    successes = sum(bool(record.get("success")) for record in records)
    return f"{successes}/{len(records)} ({successes / len(records):.0%})"


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="ReportArial-Bold",
            fontSize=22,
            leading=28,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=6 * mm,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontName="ReportArial",
            fontSize=10,
            leading=15,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=7 * mm,
        ),
        "h1": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading1"],
            fontName="ReportArial-Bold",
            fontSize=15,
            leading=19,
            textColor=TEAL,
            spaceBefore=5 * mm,
            spaceAfter=2.5 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "SubHeading",
            parent=base["Heading2"],
            fontName="ReportArial-Bold",
            fontSize=11,
            leading=15,
            textColor=INK,
            spaceBefore=3 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "BodyTextVN",
            parent=base["BodyText"],
            fontName="ReportArial",
            fontSize=9,
            leading=13.5,
            textColor=INK,
            spaceAfter=2.5 * mm,
        ),
        "small": ParagraphStyle(
            "SmallTextVN",
            parent=base["BodyText"],
            fontName="ReportArial",
            fontSize=7.5,
            leading=10.5,
            textColor=MUTED,
            spaceAfter=1.5 * mm,
        ),
        "table": ParagraphStyle(
            "TableTextVN",
            parent=base["BodyText"],
            fontName="ReportArial",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "TableHeadVN",
            parent=base["BodyText"],
            fontName="ReportArial-Bold",
            fontSize=7.5,
            leading=10,
            textColor=WHITE,
        ),
        "callout": ParagraphStyle(
            "CalloutVN",
            parent=base["BodyText"],
            fontName="ReportArial-Bold",
            fontSize=9,
            leading=13,
            textColor=INK,
        ),
    }


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def draw_page(canvas: object, document: SimpleDocTemplate) -> None:
    canvas.saveState()
    page_width, _ = A4
    canvas.setStrokeColor(colors.HexColor("#D7E0E4"))
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, page_width - 18 * mm, 15 * mm)
    canvas.setFont("ReportArial", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Đánh giá Agent đặt vé máy bay | Lab 3")
    canvas.drawRightString(page_width - 18 * mm, 10 * mm, f"Trang {document.page}")
    canvas.restoreState()


def build_report() -> None:
    register_vietnamese_fonts()
    styles = make_styles()
    records = {
        "ReAct": read_runs("react"),
        "Plan-then-Execute": read_runs("plan_execute"),
        "Hybrid": read_runs("hybrid"),
    }

    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=21 * mm,
        title="Đánh giá các mẫu thiết kế Agent đặt vé máy bay",
        author="Báo cáo Lab 3",
    )
    story: list[object] = [
        Spacer(1, 8 * mm),
        paragraph("BÁO CÁO ĐÁNH GIÁ", styles["title"]),
        paragraph("Các mẫu thiết kế Agent đặt vé máy bay", styles["subtitle"]),
        paragraph(
            f'Mã nguồn công khai: <link href="{GITHUB_URL}" color="#0E7775">'
            "github.com/ElicBug/Flight-booking-agent</link>",
            styles["small"],
        ),
        HRFlowable(width="100%", thickness=1.4, color=TEAL, spaceAfter=5 * mm),
        paragraph(
            "Tổng hợp số liệu CLI hiện có và đánh giá hành vi của ReAct, "
            "Plan-then-Execute, Hybrid.",
            styles["body"],
        ),
        paragraph(
            "Ngày tổng hợp: 06-10-2026. Mỗi kiến trúc hiện có một lượt chạy được lưu; "
            "kết luận dưới đây là quan sát ban đầu, chưa phải benchmark thống kê.",
            styles["small"],
        ),
        paragraph("1. Kịch bản thử nghiệm", styles["h1"]),
        paragraph(
            "<b>Luồng booking suôn sẻ:</b> ReAct tìm chuyến, kiểm tra ghế, đặt, thanh toán "
            "và xác minh booking. Lượt này đạt mục tiêu theo kiểm tra của Harness.",
            styles["body"],
        ),
        paragraph(
            "<b>Ngày bay không khớp constraint:</b> Plan-then-Execute và Hybrid đều bị "
            "Harness chặn tại search_flights; không tạo booking.",
            styles["body"],
        ),
        paragraph(
            "Unit test riêng kiểm tra hard constraint ngày, duyệt/từ chối hành động, "
            "ngân sách, phát hiện lặp, bế tắc và tham chiếu state trong kế hoạch. "
            "Đây không phải lượt benchmark gọi LLM.",
            styles["body"],
        ),
        paragraph(
            "Chưa có log CLI cho tình huống ghế hết chỗ rồi chọn chuyến khác hoặc không có "
            "chuyến phù hợp; không suy diễn kết quả cho các tình huống này.",
            styles["small"],
        ),
        paragraph("2. So sánh số liệu ghi nhận", styles["h1"]),
    ]

    table_data = [[
        paragraph("Kiến trúc", styles["table_head"]),
        paragraph("Số lượt", styles["table_head"]),
        paragraph("Token TB", styles["table_head"]),
        paragraph("Giây TB", styles["table_head"]),
        paragraph("Bước Harness TB", styles["table_head"]),
        paragraph("Booking hợp lệ", styles["table_head"]),
    ]]
    for name in ("ReAct", "Plan-then-Execute", "Hybrid"):
        run_set = records[name]
        table_data.append([
            paragraph(name, styles["table"]),
            paragraph(str(len(run_set)), styles["table"]),
            paragraph(mean(run_set, "model_tokens", 0), styles["table"]),
            paragraph(mean(run_set, "elapsed_seconds", 3), styles["table"]),
            paragraph(mean(run_set, "tool_steps", 1), styles["table"]),
            paragraph(success_ratio(run_set), styles["table"]),
        ])
    metrics_table = Table(
        table_data,
        colWidths=[36 * mm, 16 * mm, 21 * mm, 20 * mm, 29 * mm, 35 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D3DDE1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        metrics_table,
        Spacer(1, 2 * mm),
        paragraph(
            "Token là tổng mỗi lượt, không phải token/vòng. Số bước Harness có thể bao gồm "
            "lần xin duyệt và lần thực thi lại sau khi được duyệt; không đồng nhất với số tool "
            "call trong trace.",
            styles["small"],
        ),
        paragraph("3. Đánh giá từng kiến trúc", styles["h1"]),
    ])

    detail = [
        (
            "A. ReAct",
            "<b>Thực tế:</b> một lượt thành công, 4.344 token, 8 bước Harness, 23,850 giây; "
            "trace có search_flights, check_seat hai lần, book_seat, pay, get_booking. "
            "Harness xác minh booking.<br/><b>Mạnh:</b> quan sát mới có thể điều khiển hành động "
            "tiếp theo; phù hợp số bước không cố định.<br/><b>Yếu:</b> có thể tăng token theo lịch sử "
            "và lặp hành động. Lượt này không có loop; log chưa ghi số vòng model hoặc token từng vòng.",
        ),
        (
            "B. Plan-then-Execute",
            "<b>Thực tế:</b> log không lưu raw plan; chỉ ghi một search_flights bị chặn do "
            "date_constraint_violation, 531 token, 3,194 giây.<br/><b>Mạnh:</b> kế hoạch cấu trúc "
            "có thể duyệt trước; lượt này có tổng token thấp.<br/><b>Yếu:</b> sai dữ liệu đầu vào "
            "có thể làm hỏng bước sau; chưa quan sát được recovery sau lỗi giữa quy trình vì booking "
            "chưa diễn ra.",
        ),
        (
            "C. Hybrid",
            "<b>Thực tế:</b> một search_flights bị Harness chặn cùng lỗi ngày, 442 token, "
            "2,574 giây; không có booking. Log chưa ghi nội dung review hoặc số lần replan.<br/>"
            "<b>Mạnh:</b> thiết kế chia nhóm bước rồi review observation, phù hợp môi trường thay đổi.<br/>"
            "<b>Yếu:</b> thêm trạng thái và lượt review khiến debug phức tạp; lượt này chưa chứng minh "
            "được khả năng phục hồi.",
        ),
    ]
    for heading, content in detail:
        story.append(KeepTogether([
            paragraph(heading, styles["h2"]),
            paragraph(content, styles["body"]),
        ]))

    story.extend([
        paragraph("4. Kết luận và khuyến nghị", styles["h1"]),
    ])
    summary = Table(
        [[paragraph(
            "Với phiên bản và dữ liệu hiện có, ReAct là baseline duy nhất đã hoàn tất booking "
            "được Harness xác minh. Hybrid là lựa chọn đáng đánh giá tiếp cho inventory biến động, "
            "nhưng chưa có bằng chứng thành công trong lượt đã ghi. Chưa nên tuyên bố tỷ lệ thành "
            "công tổng quát từ mẫu n=1.",
            styles["callout"],
        )]],
        colWidths=[157 * mm],
    )
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.8, TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend([
        summary,
        Spacer(1, 3 * mm),
        paragraph(
            "Để so sánh chắc chắn hơn: dùng cùng model, constraints và inventory; chạy ít nhất "
            "10 kịch bản, mỗi kịch bản 3 lần; lưu số lần gọi model, token theo lượt, raw plan/review "
            "đã loại dữ liệu nhạy cảm, replan count và kết quả verify_booking.",
            styles["body"],
        ),
    ])

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(f"PDF created: {OUTPUT}")


if __name__ == "__main__":
    build_report()