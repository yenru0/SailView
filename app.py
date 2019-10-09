#import markdown
import mistune
from mdx_gfm import GithubFlavoredMarkdownExtension
from flask import Flask, render_template_string, redirect, render_template, url_for, abort, request
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

output_template = """{{% extends 'document_layout.html' %}}
{{% block content %}}
{0}
{{% endblock %}}
"""

app = Flask(__name__)

def composePath(*args:str):
    return "/".join([i for p in args
                        for i in p.split("/")
                        if i])
app.jinja_env.globals.update(composePath=composePath)

def GFM_LMX(document_path, filename):
    lastendpos = 0
    basefilename = os.path.splitext(filename)[0]
    with open(composePath(document_path, "/{}".format(filename)), 'r', encoding='utf-8') as f:
        output = output_template.format(md(f.read()))
    while 1:
        n = 0
        t = latex_re.search(output, lastendpos)
        if t:

            if not (os.path.isdir(composePath("dummy/", "{0}".format(document_path)))):
                os.makedirs(composePath("dummy/", "{0}".format(document_path)))
            with open(composePath("dummy/", document_path, "/{0}{1}.tex".format(basefilename, n)), 'w', encoding='utf-8') as f:
                f.write(LATEX_Cs % t.group(2))
            if not (os.path.isdir(composePath("dummy/", document_path, "." + basefilename))):
                os.makedirs(composePath("dummy/", document_path, "." + basefilename))
            op = sp.call(
                "xelatex --no-pdf --output-directory={0} -interaction=batchmode --halt-on-error {1}".format(composePath("dummy/", document_path, "."+ basefilename), composePath("dummy/", document_path, "/{0}{1}.tex".format(basefilename, n)))
            )

            if op == 1:
                print(composePath(document_path, basefilename + str(n) + ".tex"), "는 이상한 것이 분명하오 요카지마.")

            else:
                op2 = sp.call(
                    "dvisvgm --clipjoin -e --no-fonts -o {0} {1}".format(
                        composePath("dummy/", document_path, "/{}{}.svg".format(basefilename, n)),
                        composePath("dummy/", document_path, ".{0}/{0}{1}.xdv".format(basefilename, n))
                    )
                )
                try:
                    with open(composePath("dummy/", document_path, "/{0}{1}.svg".format(basefilename, n)), 'r', encoding='utf-8') as f:
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
    with open(composePath("templates/", document_path, "/{}.html".format(basefilename)), 'w', encoding='utf-8') as f:
        f.write(GFM_LMX(document_path, filename))

def compile_by_path(document_path_with_file):
    basefilename = os.path.splitext(os.path.basename(document_path_with_file))[0] + ".md"
    document_path = os.path.dirname(document_path_with_file)
    compile(document_path, basefilename)

def compile_all():
    for p, ds, fns in os.walk(topdir):
        for d in ds:
            if not os.path.isdir(composePath("templates/", p, d)):
                os.makedirs(composePath("templates/", p, d))
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
@app.route("/docs")
def showDocs():
    return showDocument("")


@app.route("/docs/<path:document_path>")
def showDocument(document_path):
    print(document_path)
    if document_path == None:
        return render_template("documentsNotFound.html")
    if os.path.isdir(composePath("templates/", topdir, document_path)):
        p, dirs, files =  next(os.walk(composePath("templates/", topdir, document_path)))
        return render_template("docs_directory.html", title_name ="MWV-" + document_path, isdir = True, path = document_path, dirs = dirs, files = files)
    elif not os.path.isfile(composePath("templates/", topdir, document_path)):
        return render_template("documentsNotFound.html")
    else:
        return render_template(composePath(topdir, document_path), title_name = os.path.basename(document_path), isdir = False, path= document_path)


@app.route("/")
@app.route("/front/")
def frontPage():
    return render_template("frontpage.html")

@app.route("/compile", methods=['POST'])
def showCompile():

    path = request.form['path']
    print(path)
    if path == None:
        path = ''
        pass
    else:
        compile_by_path(composePath(topdir, path))
    return redirect(url_for('showDocument', document_path=path))



if __name__ == '__main__':
    if not (os.path.isdir("dummy")):
        os.makedirs("dummy")
    if not (os.path.isdir("documents")):
        os.makedirs("documents")
    if not (os.path.isdir("templates/documents")):
        os.makedirs("templates/documents")

    app.run(host="192.168.0.5", port="54321", debug=True)
    print(composePath("/document/recgetx/", "/syment/", "krist/"))
    #mainWindow()