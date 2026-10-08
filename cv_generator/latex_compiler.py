"""
latex_compiler.py
=================
Compiles LaTeX Resume Source to PDF using system pdflatex.
If pdflatex fails due to special characters, automatically falls back
to the native executive ATS PDF generator (pdf_compiler.py) to guarantee
a 100% successful PDF output for every job.
"""

import os
import subprocess
import shutil
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger("latex_compiler")

def compile_latex_to_pdf(tex_code: str, output_pdf_path: str, output_tex_path: str = None, profile: dict = None) -> bool:
    """
    Saves tex_code to output_tex_path and attempts to compile it into output_pdf_path using pdflatex.
    If pdflatex errors out, seamlessly falls back to pdf_compiler.py so a valid PDF is always created.
    """
    out_pdf = Path(output_pdf_path).resolve()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    
    if output_tex_path:
        out_tex = Path(output_tex_path).resolve()
        out_tex.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(out_tex, "w", encoding="utf-8") as f:
                f.write(tex_code)
            logger.info("Saved raw LaTeX source for Overleaf: %s", out_tex)
        except Exception as e:
            logger.warning("Could not save .tex file: %s", e)

    # 1. Try pdflatex / xelatex if available
    latex_bin = shutil.which("pdflatex") or shutil.which("xelatex")
    compiled_via_latex = False

    if latex_bin:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_tex = Path(tmpdir) / "resume.tex"
            with open(tmp_tex, "w", encoding="utf-8") as f:
                f.write(tex_code)
            
            try:
                cmd = [latex_bin, "-interaction=nonstopmode", "-output-directory", tmpdir, str(tmp_tex)]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
                gen_pdf = Path(tmpdir) / "resume.pdf"
                if gen_pdf.exists() and gen_pdf.stat().st_size > 1000:
                    shutil.copyfile(gen_pdf, out_pdf)
                    logger.info("LaTeX compiled successfully to ATS-PDF: %s", out_pdf)
                    compiled_via_latex = True
            except Exception as e:
                logger.warning("LaTeX compiler notice: %s. Using PDF generator fallback.", e)

    if compiled_via_latex:
        return True

    # 2. Robust Fallback: Use native ATS PDF compiler
    if profile:
        try:
            from pdf_compiler import compile_pdf_resume
            compile_pdf_resume(profile, str(out_pdf))
            logger.info("Fallback ATS PDF compiled successfully: %s", out_pdf)
            return True
        except Exception as pe:
            logger.error("Fallback PDF compilation failed: %s", pe)

    return False
