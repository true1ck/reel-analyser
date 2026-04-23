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
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Reel Analyser Report", border=False, ln=True, align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def generate_pdf(markdown_text: str, output_path: Path, title: str = "Analysis Report"):
    """
    Generate a PDF file from markdown text.
    Simplified markdown parser for PDF generation.
    """
    pdf = AnalysisPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, title, ln=True)
    pdf.ln(5)

    # Process lines
    lines = markdown_text.split("\n")
    
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
            
        # Headers
        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.ln(5)
            pdf.cell(0, 10, line[3:], ln=True)
            pdf.ln(2)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.ln(3)
            pdf.cell(0, 8, line[4:], ln=True)
            pdf.ln(1)
        # Bullet points
        elif line.startswith("- "):
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, f"• {line[2:]}")
        # Numbered list
        elif re.match(r"^\d+\.", line):
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, line)
        # Bold text handling (simple)
        elif "**" in line:
            pdf.set_font("Helvetica", "", 10)
            clean_line = line.replace("**", "")
            pdf.multi_cell(0, 6, clean_line)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, line)

    pdf.output(str(output_path))
    return output_path
