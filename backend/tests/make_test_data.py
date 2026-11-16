"""Generate deterministic synthetic DocTrace acceptance data.

Scenario constants are the single source of truth for documents and
ground_truth.json. Application output is never read. PyMuPDF is used only to
verify generated PDFs and is already required by the backend extractor.
"""
from __future__ import annotations

import hashlib, json, os, random, re, shutil, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pymupdf as fitz
except ImportError:  # PyMuPDF versions before the pymupdf import name
    import fitz
from docx import Document
from docx.shared import Pt
from openpyxl import Workbook, load_workbook
from openpyxl.packaging.core import DocumentProperties
from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

SEED = 20261114
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
HELDOUT = DATA / "heldout"
ROBUST = DATA / "robustness"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

PROJECTS = {
    "medsaathi": {"id": "MS-2026-01", "name": "MedSaathi", "set": "dev"},
    "agrisense": {"id": "AS-2026-04", "name": "AgriSense", "set": "dev"},
    "nanogrid": {"id": "NG-2026-09", "name": "NanoGrid", "set": "dev"},
    "waterwise": {"id": "WW-2026-03", "name": "WaterWise", "set": "dev"},
    "harborlight": {"id": "HL-2027-02", "name": "HarborLight", "set": "heldout"},
    "orchardeye": {"id": "OE-2027-07", "name": "OrchardEye", "set": "heldout"},
}

FILES = [
    ("medsaathi_proposal.pdf","medsaathi","pdf","2026-11-03","proposal","dev"),
    ("medsaathi_meeting.docx","medsaathi","docx","2026-11-07","meeting notes","dev"),
    ("medsaathi_receipt.png","medsaathi","png","2026-11-09","scanned receipt","dev"),
    ("medsaathi_receipt.jpg","medsaathi","jpg","2026-11-09","scanned receipt duplicate","dev"),
    ("medsaathi_receipt_scan.pdf","medsaathi","pdf-image","2026-11-09","image-only receipt","dev"),
    ("medsaathi_budget.xlsx","medsaathi","xlsx","2026-11-10","budget workbook","dev"),
    ("medsaathi_final_draft.pdf","medsaathi","pdf","2026-11-14","draft report","dev"),
    ("agrisense_brief.pdf","agrisense","pdf","2026-11-04","distractor project","dev"),
    ("lecture_notes.pdf","none","pdf","2026-11-02","unrelated distractor","dev"),
    ("nanogrid_change_request.pdf","nanogrid","pdf","2026-10-02","change request","dev"),
    ("nanogrid_approval.docx","nanogrid","docx","2026-10-05","approval letter","dev"),
    ("nanogrid_final.pdf","nanogrid","pdf","2026-10-12","final report","dev"),
    ("waterwise_plan.docx","waterwise","docx","2026-09-01","clean plan","dev"),
    ("waterwise_report.xlsx","waterwise","xlsx","2026-09-20","clean report","dev"),
    ("harborlight_request.pdf","harborlight","pdf","2027-01-05","held-out request","heldout"),
    ("harborlight_approval.docx","harborlight","docx","2027-01-08","held-out approval","heldout"),
    ("harborlight_final.xlsx","harborlight","xlsx","2027-01-20","held-out final","heldout"),
    ("orchardeye_plan.pdf","orchardeye","pdf","2027-02-03","held-out plan","heldout"),
    ("orchardeye_review.docx","orchardeye","docx","2027-02-11","held-out review","heldout"),
    ("orchardeye_final.pdf","orchardeye","pdf","2027-02-18","held-out final","heldout"),
    ("harbor_safety_notes.pdf","none","pdf","2027-01-04","held-out name trap","heldout"),
    ("orchard_due_dates.xlsx","none","xlsx","2027-02-01","held-out date trap","heldout"),
]

FACTS = [
    ("medsaathi_proposal.pdf","project_budget","Rs 50,000","50000","INR","approved"),
    ("medsaathi_proposal.pdf","submission_deadline","20 November 2026","2026-11-20",None,"approved"),
    ("medsaathi_meeting.docx","project_budget","Rs. 65,000","65000","INR","proposed"),
    ("medsaathi_meeting.docx","submission_deadline","25 November 2026","2026-11-25",None,"proposed"),
    ("medsaathi_receipt.png","expense_item","Rs 4,250","4250","INR","stated"),
    ("medsaathi_receipt.jpg","expense_item","Rs 4,250","4250","INR","stated"),
    ("medsaathi_receipt_scan.pdf","expense_item","Rs 4,250","4250","INR","stated"),
    ("medsaathi_budget.xlsx","project_budget","INR 65000","65000","INR","stated"),
    ("medsaathi_budget.xlsx","expense_item","4250","4250","INR","stated"),
    ("medsaathi_final_draft.pdf","project_budget","₹50,000","50000","INR","stated"),
    ("medsaathi_final_draft.pdf","submission_deadline","20/11/2026","2026-11-20",None,"stated"),
    ("agrisense_brief.pdf","project_budget","Rs 40,000","40000","INR","approved"),
    ("agrisense_brief.pdf","submission_deadline","20 November 2026","2026-11-20",None,"approved"),
    ("nanogrid_change_request.pdf","project_budget","Rs 1.5 lakh","150000","INR","proposed"),
    ("nanogrid_approval.docx","project_budget","INR 150000","150000","INR","approved"),
    ("nanogrid_final.pdf","project_budget","₹1,50,000","150000","INR","stated"),
    ("waterwise_plan.docx","project_budget","Rs. 72,500","72500","INR","approved"),
    ("waterwise_report.xlsx","project_budget","72500","72500","INR","stated"),
    ("harborlight_request.pdf","project_budget","Rs 88,000","88000","INR","proposed"),
    ("harborlight_approval.docx","project_budget","INR 88000","88000","INR","approved"),
    ("harborlight_final.xlsx","project_budget","88000","88000","INR","stated"),
    ("orchardeye_plan.pdf","project_budget","₹96,000","96000","INR","approved"),
    ("orchardeye_review.docx","submission_deadline","Mar 2, 2027","2027-03-02",None,"proposed"),
    ("orchardeye_final.pdf","project_budget","INR 96000","96000","INR","stated"),
]

RELATIONSHIPS = [
    ("medsaathi_proposal.pdf","medsaathi_meeting.docx","same_topic","same project id and proposal discussed"),
    ("medsaathi_meeting.docx","medsaathi_final_draft.pdf","references","draft cites 7 November meeting"),
    ("medsaathi_meeting.docx","medsaathi_budget.xlsx","supports","requested 65000 appears in workbook"),
    ("medsaathi_receipt.png","medsaathi_budget.xlsx","supports","pilot kits 4250 is a line item"),
    ("medsaathi_receipt.jpg","medsaathi_budget.xlsx","supports","duplicate scan supports pilot kits line"),
    ("medsaathi_receipt_scan.pdf","medsaathi_budget.xlsx","supports","image-only receipt supports pilot kits line"),
    ("medsaathi_proposal.pdf","medsaathi_final_draft.pdf","revision_of","draft retains proposal values and id"),
    ("nanogrid_change_request.pdf","nanogrid_approval.docx","supports","letter explicitly approves request"),
    ("nanogrid_approval.docx","nanogrid_final.pdf","supports","final uses approved value"),
    ("waterwise_plan.docx","waterwise_report.xlsx","same_topic","same id and unchanged amount"),
    ("harborlight_request.pdf","harborlight_approval.docx","supports","held-out approval names request"),
    ("harborlight_approval.docx","harborlight_final.xlsx","supports","held-out final uses sanctioned amount"),
    ("orchardeye_plan.pdf","orchardeye_review.docx","same_topic","held-out project id"),
    ("orchardeye_review.docx","orchardeye_final.pdf","references","held-out final cites review"),
]

MUST_NOT_LINK = [
    ("medsaathi_proposal.pdf","agrisense_brief.pdf","same guide and deadline; different ids"),
    ("medsaathi_proposal.pdf","lecture_notes.pdf","same due date; lecture is not project evidence"),
    ("medsaathi_final_draft.pdf","agrisense_brief.pdf","same deadline; different ids"),
    ("harborlight_request.pdf","harbor_safety_notes.pdf","shared Harbor word only"),
    ("orchardeye_plan.pdf","orchard_due_dates.xlsx","shared orchard/date language only"),
]

TIMELINE = [
    ("medsaathi_proposal.pdf","2026-11-03","Proposal approved as submitted"),
    ("medsaathi_meeting.docx","2026-11-07","Budget and deadline increase proposed"),
    ("medsaathi_receipt_scan.pdf","2026-11-09","Pilot kits purchased"),
    ("medsaathi_budget.xlsx","2026-11-10","Revised workbook prepared"),
    ("medsaathi_final_draft.pdf","2026-11-14","Draft prepared"),
    ("nanogrid_change_request.pdf","2026-10-02","Increase requested"),
    ("nanogrid_approval.docx","2026-10-05","Increase approved"),
    ("nanogrid_final.pdf","2026-10-12","Final issued"),
    ("waterwise_plan.docx","2026-09-01","Plan approved"),
    ("waterwise_report.xlsx","2026-09-20","Completion recorded"),
    ("harborlight_request.pdf","2027-01-05","Lighting budget requested"),
    ("harborlight_approval.docx","2027-01-08","Lighting budget sanctioned"),
    ("harborlight_final.xlsx","2027-01-20","Close-out recorded"),
    ("orchardeye_plan.pdf","2027-02-03","Plan approved"),
    ("orchardeye_review.docx","2027-02-11","Date move proposed"),
    ("orchardeye_final.pdf","2027-02-18","Final prepared"),
]

def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)

def font_path() -> Path:
    candidates = [
        Path(os.environ.get("DOCTRACE_TEST_FONT","")),
        Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/seguisym.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            candidate = TTFont("Candidate", str(path))
            if 0x20B9 in candidate.face.charWidths:
                return path
    raise RuntimeError("Set DOCTRACE_TEST_FONT to a TrueType font containing U+20B9")

def canonical_zip(path: Path, story_date: str) -> None:
    with zipfile.ZipFile(path) as source:
        items = [(n, source.read(n), source.getinfo(n).compress_type) for n in source.namelist()]
    temp = path.with_suffix(path.suffix + ".canonical")
    with zipfile.ZipFile(temp, "w") as target:
        for name, payload, compression in sorted(items):
            if name == "docProps/core.xml":
                fixed = f"{story_date}T00:00:00Z".encode("ascii")
                payload = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
                    lambda match: match.group(1) + fixed + match.group(2),
                    payload,
                )
            info = zipfile.ZipInfo(name, ZIP_EPOCH)
            info.compress_type, info.create_system, info.external_attr = compression, 3, 0o600 << 16
            target.writestr(info, payload)
    temp.replace(path)

def stamp(path: Path, date: str) -> None:
    when = dt(date).timestamp()
    os.utime(path, (when, when))

def wrap(text: str, limit: int = 92) -> list[str]:
    result, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if current and len(candidate) > limit:
            result.append(current); current = word
        else:
            current = candidate
    return result + ([current] if current else [])

def pdf(path: Path, date: str, title: str, pages: list[list[str]], font: Path) -> None:
    pdfmetrics.registerFont(TTFont("DocTraceRupee", str(font)))
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1, pageCompression=1)
    c.setTitle(title); c.setAuthor("DocTrace Synthetic Fixtures")
    c.setCreator("DocTrace deterministic generator"); c.setSubject("Synthetic evidence only")
    compact = date.replace("-", "")
    c._doc.info._dateFormatter = lambda *args: f"D:{compact}120000+00'00'"
    width, height = A4
    for number, lines in enumerate(pages, 1):
        c.setFont("DocTraceRupee", 16); c.drawString(54, height-62, title)
        c.setFont("DocTraceRupee", 9); c.drawRightString(width-54, height-62, f"Page {number}")
        y = height-100
        for line in lines:
            for part in wrap(line):
                c.setFont("DocTraceRupee", 11); c.drawString(54, y, part); y -= 18
            y -= 5
        c.showPage()
    c.save(); stamp(path, date)

def docx(path: Path, date: str, title: str, paragraphs: list[str], rows: list[tuple[str,str]]) -> None:
    d = Document()
    d.core_properties.title, d.core_properties.author = title, "DocTrace Synthetic Fixtures"
    d.core_properties.created = d.core_properties.modified = dt(date)
    d.add_heading(title, 1)
    for text in paragraphs: d.add_paragraph(text)
    table = d.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Field", "Recorded value"
    for left, right in rows:
        cells = table.add_row().cells; cells[0].text, cells[1].text = left, right
    d.styles["Normal"].font.name = "Arial"; d.styles["Normal"].font.size = Pt(10)
    d.save(path); canonical_zip(path, date); stamp(path, date)

def xlsx(path: Path, date: str, title: str, rows: list[tuple[str,Any]], revisions: list[tuple[str,str,str]]) -> None:
    wb = Workbook(); ws = wb.active; ws.title = "Summary"
    ws["A1"], ws["A2"] = title, "Literal values; no formulas."
    for number, (label, value) in enumerate(rows, 4):
        ws.cell(number, 1, label); ws.cell(number, 2, value)
    ws["A12"] = "TOTAL"; ws["B12"] = next(v for k,v in rows if k == "TOTAL")
    log = wb.create_sheet("Revision Log"); log.append(["Date","Status","Note"])
    for row in revisions: log.append(row)
    naive = dt(date).replace(tzinfo=None)
    wb.properties = DocumentProperties(creator="DocTrace Synthetic Fixtures", title=title, created=naive, modified=naive)
    wb.calculation.fullCalcOnLoad = wb.calculation.forceFullCalc = False
    wb.save(path); canonical_zip(path, date); stamp(path, date)

def scan(font: Path) -> Image.Image:
    rng = random.Random(SEED); image = Image.new("L", (1500,920), 242); draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(str(font),48); body = ImageFont.truetype(str(font),35); small = ImageFont.truetype(str(font),27)
    draw.text((100,80),"CAMPUS MEDICAL SUPPLIES",font=title,fill=15)
    draw.text((100,160),"Receipt # PK-0911     09/11/2026",font=body,fill=25)
    draw.text((100,245),"Project: MedSaathi / MS-2026-01",font=body,fill=20)
    draw.line((90,315,1390,315),fill=70,width=3)
    draw.text((110,370),"Pilot kits    qty 10",font=body,fill=18)
    draw.text((925,370),"Rs 4,250",font=body,fill=38)
    draw.text((110,465),"Paid; training aids only",font=small,fill=35)
    draw.text((110,555),"TOTAL",font=title,fill=12); draw.text((930,555),"₹4,250",font=title,fill=72)
    for _ in range(8500):
        image.putpixel((rng.randrange(image.width),rng.randrange(image.height)), rng.choice((0,35,205,255)))
    return image.filter(ImageFilter.GaussianBlur(.75)).rotate(1.35,Image.Resampling.BICUBIC,fillcolor=245)

def scans(font: Path) -> None:
    image = scan(font)
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Creation Time", "2026-11-09T12:00:00Z")
    p = DATA/"medsaathi_receipt.png"; image.save(p,"PNG",optimize=False,compress_level=9,pnginfo=png_info); stamp(p,"2026-11-09")
    p = DATA/"medsaathi_receipt.jpg"; exif=Image.Exif(); exif[306]=exif[36867]="2026:11:09 12:00:00"
    image.save(p,"JPEG",quality=82,subsampling=0,optimize=False,progressive=False,exif=exif); stamp(p,"2026-11-09")
    p = DATA/"medsaathi_receipt_scan.pdf"; c=canvas.Canvas(str(p),pagesize=A4,invariant=1,pageCompression=1)
    c.setTitle("MedSaathi scanned receipt"); c.setAuthor("DocTrace Synthetic Fixtures")
    c._doc.info._dateFormatter=lambda *args:"D:20261109120000+00'00'"
    width,height=A4; c.drawImage(ImageReader(image.convert("RGB")),25,160,width=width-50,height=height-260,preserveAspectRatio=True)
    c.showPage(); c.save(); stamp(p,"2026-11-09")

def generate_documents(font: Path) -> None:
    pdf(DATA/"medsaathi_proposal.pdf","2026-11-03","MedSaathi Proposal MS-2026-01",[
        ["Student Innovation Cell","Guide: Dr Mira Sen","The review continues on later pages."],
        ["Need statement","Medicine reminder cards and a supervised pilot."],
        ["Approval record dated 3 November 2026.","MedSaathi MS-2026-01 is approved as submitted.","Sanctioned budget: Rs 50,000.","Final submission deadline: 20 November 2026."]],font)
    docx(DATA/"medsaathi_meeting.docx","2026-11-07","MedSaathi coordination meeting",[
        "Minutes for MS-2026-01, held 7 November 2026 with guide Dr Mira Sen.",
        "The team proposed raising the total cost to Rs. 65,000 and requested moving the due date to 25 November 2026.",
        "These changes are tentative. No approval or sanction was recorded."],
        [("Budget request","Rs. 65,000 — proposed"),("Final submission","25 November 2026 — requested")])
    scans(font)
    xlsx(DATA/"medsaathi_budget.xlsx","2026-11-10","MedSaathi MS-2026-01 budget",[
        ("Pilot kits",4250),("Reminder-card printing",6750),("Tablet devices",18000),("Field travel",7000),
        ("Workshop venue",8500),("Accessibility review",9500),("Contingency",11000),("TOTAL",65000)],
        [("2026-11-07","proposed","Meeting requested INR 65000"),("2026-11-10","stated","Approval not recorded")])
    pdf(DATA/"medsaathi_final_draft.pdf","2026-11-14","MedSaathi Final Report Draft",[[
        "Draft for MS-2026-01 dated 14 November 2026 cites the coordination meeting held on 7 November 2026.",
        "This draft still states a budget of ₹50,000 and final submission on 20/11/2026.",
        "It does not record approval of the requested changes."]],font)
    pdf(DATA/"agrisense_brief.pdf","2026-11-04","AgriSense Brief AS-2026-04",[[
        "Guide: Dr Mira Sen. This is a separate agriculture project.","Approved allocated funds: Rs 40,000.",
        "The confirmed deadline is 20 November 2026.","No MS-2026-01 document is referenced."]],font)
    pdf(DATA/"lecture_notes.pdf","2026-11-02","Information Retrieval Lecture Notes",[[
        "Class exercise: rank a collection using cosine similarity.","Homework due date: 20 November 2026.",
        "This is not a project record and contains no project identifier."]],font)
    pdf(DATA/"nanogrid_change_request.pdf","2026-10-02","NanoGrid Request NG-2026-09",[[
        "On 2 October 2026 the team proposed a revised budget of Rs 1.5 lakh.",
        "This request is not approval; a signed letter must follow."]],font)
    docx(DATA/"nanogrid_approval.docx","2026-10-05","NanoGrid approval letter",[
        "Dated 5 October 2026. Re: change request NG-2026-09.",
        "The committee approved and sanctioned allocated funds of INR 150000."],
        [("Decision","approved"),("Authorized budget","INR 150000")])
    pdf(DATA/"nanogrid_final.pdf","2026-10-12","NanoGrid Final NG-2026-09",[[
        "Final report dated 12 October 2026.","The project used the approved budget of ₹1,50,000.",
        "Approval letter dated 5 October 2026 is cited."]],font)
    docx(DATA/"waterwise_plan.docx","2026-09-01","WaterWise plan WW-2026-03",[
        "Plan approved 1 September 2026.","Confirmed budget Rs. 72,500; final submission Sep 20, 2026."],
        [("Project","WW-2026-03"),("Budget","Rs. 72,500 — approved")])
    xlsx(DATA/"waterwise_report.xlsx","2026-09-20","WaterWise WW-2026-03 completion",[
        ("Equipment",50000),("Outreach",12500),("Testing",10000),("TOTAL",72500)],
        [("2026-09-20","confirmed","Closed at approved amount")])
    pdf(HELDOUT/"harborlight_request.pdf","2027-01-05","HarborLight note HL-2027-02",[[
        "On Jan 5, 2027 the crew asked for a total cost of Rs 88,000.","The figure is requested, not sanctioned.",
        "Final submission is Jan 22, 2027."]],font)
    docx(HELDOUT/"harborlight_approval.docx","2027-01-08","HarborLight authorization",[
        "8 January 2027; reference HL-2027-02.","The board sanctioned allocated funds INR 88000 and confirmed the request."],
        [("Authority","Harbor board"),("Decision","sanctioned")])
    xlsx(HELDOUT/"harborlight_final.xlsx","2027-01-20","HL-2027-02 lighting close-out",[
        ("Fixtures",63000),("Installation",25000),("TOTAL",88000)],
        [("2027-01-08","approved","Board authorization"),("2027-01-20","stated","Close-out")])
    pdf(HELDOUT/"orchardeye_plan.pdf","2027-02-03","OrchardEye Plan OE-2027-07",[[
        "Confirmed on 3 February 2027.","Budget ₹96,000 is approved.","Final submission: 28 February 2027."]],font)
    docx(HELDOUT/"orchardeye_review.docx","2027-02-11","OrchardEye field review",[
        "Review of OE-2027-07 on 11 February 2027.","The group tentatively requested final submission on Mar 2, 2027.",
        "No approval was captured."],[("Due-date request","Mar 2, 2027"),("Status","tentative")])
    pdf(HELDOUT/"orchardeye_final.pdf","2027-02-18","OrchardEye Final OE-2027-07",[[
        "Prepared 18 February 2027 and citing the 11 February field review.","Total cost INR 96000.",
        "The approved date remains 28 February 2027."]],font)
    pdf(HELDOUT/"harbor_safety_notes.pdf","2027-01-04","Harbor Safety Seminar",[[
        "A public lecture about harbor lights and navigation.","It is not project HL-2027-02 and has no allocated funds."]],font)
    xlsx(HELDOUT/"orchard_due_dates.xlsx","2027-02-01","Orchard class due dates",[
        ("Botany essay due 28 February 2027",0),("TOTAL",0)],
        [("2027-02-01","stated","Course calendar, not a project")])

def robustness() -> None:
    (ROBUST/"empty.pdf").write_bytes(b"")
    (ROBUST/"corrupted.pdf").write_bytes(b"%PDF-1.7\nthis is deliberately truncated\n")
    image=Image.new("RGB",(4,4),"white"); temp=ROBUST/"_wrong.png"; image.save(temp,"PNG",optimize=False)
    (ROBUST/"wrong_extension.pdf").write_bytes(temp.read_bytes()); temp.unlink()
    (ROBUST/"unsupported.txt").write_text("Unsupported fixture; .txt/.eml ingestion is not implemented.\n",encoding="utf-8",newline="\n")
    for path in ROBUST.iterdir(): stamp(path,"2026-11-14")

def truth(font: Path) -> dict[str,Any]:
    held = {row[0] for row in FILES if row[5] == "heldout"}
    return {
        "schemaVersion":1,"seed":SEED,
        "description":"Small synthetic DocTrace data; not a general accuracy benchmark.",
        "singleSourceOfTruth":"Scenario constants in backend/tests/make_test_data.py",
        "rupeeFont":font.name,"unsupportedFormats":[".txt",".eml"],
        "oversizedFixture":{"stored":False,"testInstruction":"Generate 25 MiB + 1 byte during the upload test."},
        "projects":PROJECTS,
        "files":[{"path":("heldout/"+n if s=="heldout" else n),"project":p,"projectId":PROJECTS.get(p,{}).get("id"),
                  "format":f,"fileDate":d,"role":r,"set":s} for n,p,f,d,r,s in FILES],
        "trueRelationships":[{"source":a,"target":b,"type":t,"reason":r,"set":("heldout" if a in held else "dev")}
                             for a,b,t,r in RELATIONSHIPS],
        "mustNotLink":[{"source":a,"target":b,"trap":r,"set":("heldout" if a in held else "dev")} for a,b,r in MUST_NOT_LINK],
        "expectedFacts":[{"document":n,"canonicalField":f,"rawValue":raw,"normalizedValue":v,"unit":u,"status":s,
                          "set":("heldout" if n in held else "dev")} for n,f,raw,v,u,s in FACTS],
        "expectedConflicts":[
            {"project":"medsaathi","canonicalField":"project_budget",
             "documents":["medsaathi_proposal.pdf","medsaathi_meeting.docx","medsaathi_budget.xlsx","medsaathi_final_draft.pdf"],
             "normalizedValues":["50000","65000"],"reason":"65000 is proposed but not approved; no winner.","winner":None},
            {"project":"medsaathi","canonicalField":"submission_deadline",
             "documents":["medsaathi_proposal.pdf","medsaathi_meeting.docx","medsaathi_final_draft.pdf"],
             "normalizedValues":["2026-11-20","2026-11-25"],"reason":"25 November is requested but not approved; no winner.","winner":None}],
        "expectedNonConflicts":[
            {"project":"nanogrid","canonicalField":"project_budget","reason":"later dated approval explains the change"},
            {"project":"waterwise","canonicalField":"project_budget","reason":"all values agree"},
            {"project":"harborlight","canonicalField":"project_budget","reason":"held-out request is approved"},
            {"pair":["medsaathi_proposal.pdf","agrisense_brief.pdf"],"canonicalField":"submission_deadline","reason":"different project clusters"}],
        "expectedTimeline":[{"document":n,"eventDate":d,"fileDate":d,"label":l,"set":("heldout" if n in held else "dev")}
                            for n,d,l in TIMELINE],
        "expectedTimelineOrder":{
            p:[n for n,d,l in TIMELINE if n.startswith(p+"_")]
            for p in ("medsaathi","nanogrid","waterwise","harborlight","orchardeye")},
        "ocrExpectedValues":[{
            "documents":["medsaathi_receipt.png","medsaathi_receipt.jpg","medsaathi_receipt_scan.pdf"],
            "field":"expense_item","item":"pilot kits","rawVariants":["Rs 4,250","₹4,250","Rs 4,25O"],
            "normalizedValue":"4250","currency":"INR","linkedDocument":"medsaathi_budget.xlsx","linkedCell":"Summary!B4"}],
        "robustnessFiles":[
            {"path":"robustness/empty.pdf","expected":"reject empty file"},
            {"path":"robustness/corrupted.pdf","expected":"readable extraction failure"},
            {"path":"robustness/wrong_extension.pdf","expected":"reject magic mismatch"},
            {"path":"robustness/unsupported.txt","expected":"reject unsupported type"}],
    }

def verify(font: Path) -> None:
    proposal=fitz.open(DATA/"medsaathi_proposal.pdf")
    assert len(proposal)==3 and "Rs 50,000" in proposal[2].get_text() and "20 November 2026" in proposal[2].get_text()
    proposal.close()
    draft=fitz.open(DATA/"medsaathi_final_draft.pdf"); text="".join(p.get_text() for p in draft); draft.close()
    assert "₹50,000" in text, f"Rupee sign failed PDF extraction with {font}"
    image_pdf=fitz.open(DATA/"medsaathi_receipt_scan.pdf"); assert not "".join(p.get_text() for p in image_pdf).strip(); image_pdf.close()
    book=load_workbook(DATA/"medsaathi_budget.xlsx",data_only=True)
    assert book["Summary"]["B12"].value==65000 and set(book.sheetnames)=={"Summary","Revision Log"}; book.close()

def manifest() -> dict[str,str]:
    return {p.relative_to(DATA).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(DATA.rglob("*")) if p.is_file() and p.name!="sha256_manifest.json"}

def main() -> None:
    if DATA.exists(): shutil.rmtree(DATA)
    HELDOUT.mkdir(parents=True); ROBUST.mkdir(parents=True)
    font=font_path(); generate_documents(font); robustness()
    (DATA/"ground_truth.json").write_text(json.dumps(truth(font),indent=2,sort_keys=True,ensure_ascii=False)+"\n",
                                         encoding="utf-8",newline="\n")
    verify(font)
    hashes=manifest()
    (DATA/"sha256_manifest.json").write_text(json.dumps(hashes,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    print(f"Generated {len(hashes)} deterministic files under {DATA}")
    print(f"Rupee font verified by extraction: {font}")

if __name__ == "__main__":
    main()
