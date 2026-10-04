"""
latex_compiler.py
=================
Compiles LaTeX Resume Source to PDF using system pdflatex/xelatex or fallbacks.
Also saves the raw .tex file for direct import into Overleaf.
"""

import os
import subprocess
import shutil
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger("latex_compiler")

def compile_latex_to_pdf(tex_code: str, output_pdf_path: str, output_tex_path: str = None) -> bool:
    """
    Saves tex_code to output_tex_path and attempts to compile it into output_pdf_path using pdflatex.
    Returns True if PDF is successfully created, False otherwise.
    """
    out_pdf = Path(output_pdf_path).resolve()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    
    if output_tex_path:
        out_tex = Path(output_tex_path).resolve()
        out_tex.parent.mkdir(parents=True, exist_ok=True)
        with open(out_tex, "w", encoding="utf-8") as f:
            f.write(tex_code)
        logger.info("Saved raw LaTeX source for Overleaf: %s", out_tex)

    # Check if pdflatex or xelatex is installed
    latex_bin = shutil.which("pdflatex") or shutil.which("xelatex")
    if not latex_bin:
        logger.warning("No LaTeX compiler (pdflatex/xelatex) found in PATH. Saving .tex file only.")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_tex = Path(tmpdir) / "resume.tex"
        with open(tmp_tex, "w", encoding="utf-8") as f:
            f.write(tex_code)
        
        try:
            # Run pdflatex twice for proper cross-references and geometry layout
            cmd = [latex_bin, "-interaction=nonstopmode", "-output-directory", tmpdir, str(tmp_tex)]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)
            
            gen_pdf = Path(tmpdir) / "resume.pdf"
            if gen_pdf.exists():
                shutil.copyfile(gen_pdf, out_pdf)
                logger.info("LaTeX compiled successfully to ATS-PDF: %s", out_pdf)
                return True
        except Exception as e:
            logger.error("LaTeX compilation error: %s", e)
            return False

    return False
