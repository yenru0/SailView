#import markdown
import mistune
from mdx_gfm import GithubFlavoredMarkdownExtension
from flask import Flask, render_template_string, redirect, render_template, url_for, abort
import re
import sys
import os
import subprocess as sp


### init
topdir = "documents/"
md = mistune.Markdown()
latex_re = re.compile(r'<pre><code class="lang-(latex|math)">(.+)</code></pre>', re.DOTALL)
math_re = re.compile(r'<pre><code class="lang-math">(.+)</code></pre>', re.DOTALL)

LATEX_Cs = r"""\documentclass[dvips]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsfonts}
\usepackage{amsthm}
\usepackage{kotex}
\usepackage{tikz}
\usepackage{tkz-euclide}
\usepackage{pgfplots}
\usepackage{tikz-3dplot}
\pgfplotsset{compat=1.16}
\thispagestyle{empty}
\setmainhangulfont{NanumGothic}
\setsanshangulfont{NanumMyeongjo}
\setmonohangulfont{D2Coding}
\begin{document}
%s
\end{document}
"""

output_template = """<!DOCTYPE html>
        <head>
            <meta charset="utf-8">
            <link rel="stylesheet" type="text/css" href="{{{{ url_for('static', filename='app.css') }}}}">
            <title>{0}</title>
        </head>
        <body>{1}</body>
        </html>"""

app = Flask(__name__)

def GFM_LMX(document_path, filename):
    lastendpos = 0
    basefilename = os.path.splitext(filename)[0]
    with open(document_path + "/{}".format(filename), 'r', encoding='utf-8') as f:
        output = output_template.format(filename, md(f.read()))
    while 1:
        n = 0
        t = latex_re.search(output, lastendpos)
        if t:

            if not (os.path.isdir("dummy/{0}".format(document_path))):
                os.makedirs("dummy/{0}".format(document_path))
            with open('dummy/{0}/{1}{2}.tex'.format(document_path, basefilename, n), 'w', encoding='utf-8') as f:
                f.write(LATEX_Cs % t.group(2))
            if not (os.path.isdir("dummy/{0}/.{1}".format(document_path, basefilename))):
                os.makedirs("dummy/{0}/.{1}".format(document_path, basefilename))
            op = sp.call("xelatex --no-pdf --output-directory=dummy/{0}/.{1}/ -interaction=batchmode --halt-on-error dummy/{0}/{1}{2}.tex".format(document_path, basefilename, n))
            if op == 1:
                pass

            else:
                op2 = sp.call("dvisvgm --clipjoin -e --no-fonts -o dummy/{0}/{1}{2}.svg dummy/{0}/.{1}/{1}{2}.xdv".format(document_path, basefilename, n))
                try:
                    with open("dummy/{0}/{1}{2}.svg".format(document_path, basefilename, n), 'r', encoding='utf-8') as f:
                        output = latex_re.sub(f.read(), output, count=1)
                except Exception as e:
                    print(e)
                    pass

            lastendpos = t.end()
            n += 1


        else:
            break
    return output

def compile(document_path, filename):
    basefilename = os.path.splitext(filename)[0]
    with open("templates/"+ document_path + "/{}.html".format(basefilename), 'w', encoding='utf-8') as f:
        f.write(GFM_LMX(document_path, filename))


def compile_all():
    for p, ds, fns in os.walk(topdir):
        for d in ds:
            if not os.path.isdir("templates/" + p + d):
                os.makedirs("templates/" + p+d)
        for fn in fns:
            ext = os.path.splitext(fn)[-1]
            if ext == ".md":
                compile(p, fn)



"""
    path, dirs, files = next(os.walk(topdir + atopdir))
    for dirname in dirs:
        print(dirname)
    print("---")
    for filename in files:
        ext = os.path.splitext(filename)[-1]
        if ext == ".md":
            print(filename)
"""
@app.route("/docs/")
def docs():
    return "docs"


@app.route("/docs/<path:document_path>")
def showDocument(document_path):
    print("R")
    return render_template(document_path)


#compile_all()

@app.route("/")
def mainWindow():
    return redirect(url_for("frontPage"))

@app.route("/front/")
def frontPage():
    return render_template("frontpage.html")

if __name__ == '__main__':
    compile_all()
    app.run( port="54321")
    #mainWindow()