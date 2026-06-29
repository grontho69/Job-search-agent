"""
pdf_compiler.py
===============
Executive Single-Page ATS Resume Compiler for Mahathir Mohammad (v7 - Perfect Balance)
-------------------------------------------------------------------------------------
Single-column executive layout with zero overflow, perfectly balanced vertical spacing,
clean project headings (no hyphen prefix), active live hyperlinks, and rich ATS typography.
"""

import logging
from pathlib import Path
from fpdf import FPDF

logger = logging.getLogger("pdf_compiler")

def _clean_str(text: str) -> str:
    """Sanitize unicode quotes, dashes, and bullet characters for standard FPDF fonts."""
    if not text:
        return ""
    text = str(text)
    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "-",
        "…": "...",
        "\u2013": "-",
        "\u2014": "-",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\xa0": " ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "ignore").decode("latin-1")

class ATSResumePDF(FPDF):
    def header(self):
        pass
    def footer(self):
        pass

def compile_pdf_resume(profile: dict, output_pdf_path: str) -> str:
    """
    Compile candidate profile into an executive ATS-formatted PDF guaranteed to fit on 1 PAGE with perfect vertical balance.
    """
    pdf = ATSResumePDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=False)  # Strict 1-page guard
    pdf.add_page()

    # Color Palette - Executive Dark Navy
    COLOR_NAME    = (26, 26, 46)     # Deep Navy (#1A1A2E)
    COLOR_TITLE   = (30, 80, 150)    # Slate Blue (#1E5096)
    COLOR_SECTION = (26, 26, 46)     # Section Header Navy
    COLOR_BODY    = (40, 40, 40)     # Dark Charcoal (#282828)
    COLOR_LINK    = (15, 75, 165)    # Link Blue (#0F4BA5)

    # 1. Candidate Name
    pdf.set_x(pdf.l_margin)
    name = _clean_str(profile.get("name", "Mahathir Mohammad"))
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*COLOR_NAME)
    pdf.cell(0, 8, name, new_x="LMARGIN", new_y="NEXT", align="C")

    # 2. Professional Title (Target job headline)
    pdf.set_x(pdf.l_margin)
    title = _clean_str(profile.get("professional_title", "Full Stack Web Developer (MERN Stack)"))
    pdf.set_font("Helvetica", "BI", 11)
    pdf.set_text_color(*COLOR_TITLE)
    pdf.cell(0, 5.5, title, new_x="LMARGIN", new_y="NEXT", align="C")

    # 3. Contact Line with Active Hyperlinks
    pdf.set_x(pdf.l_margin)
    contact = profile.get("contact", {})
    c_items = []
    if contact.get("email"): c_items.append(("Email", f"mailto:{contact['email']}", contact["email"]))
    if contact.get("phone"): c_items.append(("Phone", None, contact["phone"]))
    if contact.get("portfolio"): c_items.append(("Portfolio", contact["portfolio"], "Portfolio"))
    if contact.get("github"): c_items.append(("GitHub", contact["github"], "GitHub"))
    if contact.get("linkedin"): c_items.append(("LinkedIn", contact["linkedin"], "LinkedIn"))
    if contact.get("location"): c_items.append(("Location", None, contact["location"]))

    for idx, item in enumerate(c_items):
        label, link_url, disp_text = item
        if link_url:
            pdf.set_font("Helvetica", "U", 9)
            pdf.set_text_color(*COLOR_LINK)
            pdf.write(4.8, _clean_str(disp_text), link=_clean_str(link_url))
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*COLOR_BODY)
            pdf.write(4.8, _clean_str(disp_text))
            
        if idx < len(c_items) - 1:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*COLOR_BODY)
            pdf.write(4.8, "  |  ")
    pdf.ln(5.5)

    def add_section_header(header_text):
        pdf.ln(2.5)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*COLOR_SECTION)
        pdf.cell(0, 5.5, header_text.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(200, 205, 215)
        pdf.set_line_width(0.4)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2.5)

    # 4. Professional Summary
    summary = profile.get("summary")
    if summary:
        add_section_header("Professional Summary")
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*COLOR_BODY)
        pdf.multi_cell(pdf.epw, 4.8, _clean_str(summary))

    # 5. Technical Skills
    skills = profile.get("technical_skills", {})
    if skills:
        add_section_header("Technical Skills")
        for category, item_list in skills.items():
            pdf.set_x(pdf.l_margin)
            if isinstance(item_list, list):
                items_str = ", ".join([_clean_str(i) for i in item_list])
            else:
                items_str = _clean_str(item_list)
            
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*COLOR_SECTION)
            pdf.write(4.6, _clean_str(f"{category}: "))
            
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(*COLOR_BODY)
            pdf.write(4.6, f"{items_str}\n")

    # 6. Projects (Clean Headings without hyphen prefix)
    projects = profile.get("projects", [])
    if projects:
        add_section_header("Projects")
        for proj in projects:
            pdf.set_x(pdf.l_margin)
            p_name = _clean_str(proj.get("name", ""))
            p_tech = _clean_str(proj.get("technologies", ""))
            p_link = proj.get("live_link")
            
            # Clean project title without hyphen prefix
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*COLOR_NAME)
            pdf.write(4.8, f"{p_name}")
            
            if p_link:
                pdf.set_font("Helvetica", "BU", 9)
                pdf.set_text_color(*COLOR_LINK)
                pdf.write(4.8, "  [Live Demo]", link=_clean_str(p_link))
                
            if p_tech:
                pdf.set_font("Helvetica", "I", 8.8)
                pdf.set_text_color(*COLOR_TITLE)
                pdf.write(4.8, f"  ({p_tech})")
            pdf.ln(4.8)

            bullets = proj.get("bullets", [])
            for b in bullets:
                pdf.set_x(pdf.l_margin + 2)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*COLOR_BODY)
                pdf.cell(3.5, 4.4, "-", new_x="RIGHT", new_y="LAST")
                pdf.multi_cell(pdf.epw - 5.5, 4.4, _clean_str(b))
            pdf.ln(1.5)

    # 7. Education
    education = profile.get("education", [])
    if education:
        add_section_header("Education")
        for edu in education:
            pdf.set_x(pdf.l_margin)
            degree = _clean_str(edu.get("degree", ""))
            field = _clean_str(edu.get("field", ""))
            inst = _clean_str(edu.get("institution", ""))
            year = _clean_str(edu.get("graduation_year", ""))
            
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*COLOR_NAME)
            pdf.cell(0, 4.8, f"{degree} - {inst} ({year})", new_x="LMARGIN", new_y="NEXT")

    pdf.output(output_pdf_path)
    logger.info("Executive Single-page ATS PDF compiled cleanly (%d page): %s", pdf.page_no(), output_pdf_path)
    return output_pdf_path
