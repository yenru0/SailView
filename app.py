"""
Project Sail Steel
"""


import mistune
from flask import Flask, render_template_string, redirect, render_template, url_for, abort, request
import re
import sys
import os
import subprocess as sp
import logging

__version__ = "0.0.1t"

"""
f: file
d: document 
***document in file***

name: name (usually using with f like fname)
path: dir + fname
dir: path except fname

dpath: document_path
fpath: file_path
"""


### init
topdir = "documents/"
md = mistune.Markdown()
latex_re = re.compile(r'<pre><code class="lang-(latex|math)">(.+?)</code></pre>', re.DOTALL)

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

output_template = """{{% extends 'layout.html' %}}
{{% block content %}}
{0}
{{% endblock %}}
"""

app = Flask(__name__)

### define default functions
def composePath(*args:str):
    return "/".join([j for p in args
                    for i in p.split("/")
                    for j in i.split("\\")
                     if j]
                    )



app.jinja_env.globals.update(composePath=composePath)


### define compile functions
def GFM_LMX(document_path):
    """

    :param document_path: example: documents/subdir.../main.md
    :return: HTML string

    :var
        lastendpos: temp,
        dir: dpath except fname,
        fname: file_name,
        bfname: fname except EXT
        dummydir: dummy dir
        dummytempdir: that store REAL dummy like .log, .aux, **.xdv**
        temptexfpath:

    """
    lastendpos = 0

    dir = os.path.dirname(document_path)
    fname = os.path.basename(document_path)
    bfname = os.path.splitext(fname)[0]

    with open(document_path, 'r', encoding='utf-8') as f:
        output = output_template.format(md(f.read()))

    while 1:
        dummydir = composePath("dummy/", dir)
        dummytempdir = composePath(dummydir, ".{}".format(bfname))
        n = 0
        t = latex_re.search(output, lastendpos)
        if t:

            if not (os.path.isdir(dummydir)):
                os.makedirs(dummydir)

            temptexfpath = composePath(dummydir, "/{}{}.tex".format(bfname, n))

            with open(temptexfpath, 'w', encoding='utf-8') as f:
                f.write(LATEX_Cs % t.group(2))
            if not (os.path.isdir(dummytempdir)):
                os.makedirs(dummytempdir)
            op = sp.call(
                "xelatex --no-pdf --output-directory={0} -interaction=batchmode --halt-on-error {1}".format(dummytempdir, temptexfpath)
            )

            if op == 1:
                print(temptexfpath, "는 이상한 것이 분명하오 요카지마.")

            else:
                tempsvgfpath = composePath(dummydir, "/{}{}.svg".format(bfname, n))
                tempdvifpath = composePath(dummytempdir, "/{}{}.xdv".format(bfname, n)) # Xelatex specific
                op2 = sp.call(
                    "dvisvgm --clipjoin -e --no-fonts -o {0} {1}".format(
                        composePath(tempsvgfpath),
                        composePath(tempdvifpath)
                    )
                )

                try:
                    with open(tempsvgfpath, 'r', encoding='utf-8') as f:
                        output = latex_re.sub(f.read(), output, count=1)
                except Exception as e:
                    print(e)
                    pass
            lastendpos = t.end()
            n += 1
        else:
            break
    return output


def compile(document_path):
    dir = os.path.dirname(document_path)
    fname = os.path.basename(document_path)
    with open(composePath("templates/", dir, "/{}.html".format(fname)), 'w', encoding='utf-8') as f:
        f.write(GFM_LMX(document_path))

##@ Deprecated
def compile_by_path(document_path_with_file):
    basefilename = os.path.splitext(os.path.basename(document_path_with_file))[0] + ".md"
    document_path = os.path.dirname(document_path_with_file)
    compile(document_path, basefilename)

### Deprecated In USER
def compile_all():
    for p, ds, fns in os.walk(topdir):
        for d in ds:
            if not os.path.isdir(composePath("templates/", p, d)):
                os.makedirs(composePath("templates/", p, d))
        for fn in fns:
            ext = os.path.splitext(fn)[-1]
            if ext == ".md":
                compile(composePath(p, fn))



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


    if os.path.isdir(composePath("templates/", topdir, document_path)):
        p, dirs, files =  next(os.walk(composePath("templates/", topdir, document_path)))
        return render_template("docs_directory.html", title ="MWV-" + document_path, isadmin = True, isfile = False, isdir = True, path = document_path, dirs = dirs, files = files)
    elif not os.path.isfile(composePath("templates/", topdir, document_path)):
        return render_template("documentsNotFound.html")
    else:
        return render_template(composePath(topdir, document_path), title = os.path.basename(document_path), isadmin = True, isfile = True, isdir = False, path= document_path)


@app.route("/")
@app.route("/front/")
def frontPage():
    return render_template("frontpage.html", title = "MarkWebView", isadmin=True)

@app.route("/compile", methods=['POST'])
def showCompile():
    path = request.form['path']
    if path == None:
        path = ''
        pass
    else:
        compile(composePath(topdir, os.path.splitext(path)[0]))
    return redirect(url_for('showDocument', document_path=path))

@app.route("/compile_dir", methods=['POST'])
def showCompile_dir():
    path = request.form['path']
    if path == None:
        path = ''
        pass
    else:
        for p, dirs, fns in os.walk(composePath(topdir, path)):
            for fn in fns:
                ext = os.path.splitext(fn)[-1]
                if ext == '.md':
                    print(composePath(p, fn))
                    compile(composePath(p, fn))

    return redirect(url_for('showDocument', document_path=path))

if __name__ == '__main__':
    if not (os.path.isdir("dummy")):
        os.makedirs("dummy")
    if not (os.path.isdir("documents")):
        os.makedirs("documents")
    if not (os.path.isdir("templates/documents")):
        os.makedirs("templates/documents")
    """
    initial setting 해야함
    """
    #compile_all()
    app.run(host="localhost", port="54321",)
    #mainWindow()