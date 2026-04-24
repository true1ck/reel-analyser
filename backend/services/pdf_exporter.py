"""
PDF Export Service — converts markdown analysis to PDF using fpdf2.
"""
from __future__ import annotations
import os
from pathlib import Path
from fpdf import FPDF
import re

class AnalysisPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, "Reel Analyser - Professional Video Analysis Report", border=False, ln=True, align="R")
        self.set_draw_color(200, 200, 200)
        self.line(15, 22, 195, 22)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def clean_text(text: str) -> str:
    """Keep only basic printable ASCII characters and newlines for PDF."""
    if not text:
        return ""
    # Strip any emojis or complex unicode that fpdf2 (standard font) can't handle
    # but keep spaces and basic punctuation
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return "".join(c for c in text if 32 <= ord(c) <= 126 or c == '\n')

def generate_pdf(markdown_text: str, output_path: Path, title: str = "Analysis Report"):
    """
    Generate a PDF file from markdown text with extreme robustness.
    """
    markdown_text = clean_text(markdown_text)
    title = clean_text(title)
    
    pdf = AnalysisPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()
    
    left_margin = 15
    w = 180 # A4 width (210) - margins (15+15)
    
    # Title
    pdf.set_x(left_margin)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(w, 10, title, align="L")
    pdf.ln(5)

    # Process lines
    lines = markdown_text.split("\n")
    
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
            
        # Ensure we always start from the left margin
        pdf.set_x(left_margin)

        # Basic Bold formatting (e.g. **Text**)
        # Note: This is a very simple implementation that just checks if the whole line is bold-ish
        # or if it starts with bold. For true markdown parsing, we'd need a real parser.
        is_bold = "**" in line
        clean_line = line.replace("**", "")

        # Headers
        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.ln(4)
            content = clean_line[3:].strip()
            if content:
                pdf.set_x(left_margin)
                pdf.multi_cell(w, 9, content)
            pdf.ln(1)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.ln(2)
            content = clean_line[4:].strip()
            if content:
                pdf.set_x(left_margin)
                pdf.multi_cell(w, 8, content)
            pdf.ln(1)
        # Bullet points
        elif line.startswith("- ") or line.startswith("* "):
            pdf.set_font("Helvetica", "", 11)
            content = clean_line[2:].strip()
            if content:
                # Use a small indent for bullets
                pdf.set_x(left_margin + 5)
                pdf.multi_cell(w - 5, 7, f"- {content}")
        # Numbered list
        elif re.match(r"^\d+\.", line):
            pdf.set_font("Helvetica", "", 11)
            # Find the first space to separate number from text
            match = re.match(r"^(\d+\.)\s*(.*)", clean_line)
            if match:
                num, content = match.groups()
                pdf.set_x(left_margin)
                pdf.multi_cell(w, 7, f"{num} {content}")
            else:
                pdf.multi_cell(w, 7, clean_line)
        else:
            # Regular text
            pdf.set_font("Helvetica", "B" if is_bold else "", 11)
            pdf.multi_cell(w, 6, clean_line)

    pdf.output(str(output_path))
    return output_path
