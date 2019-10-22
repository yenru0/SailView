"""
Project Sail Steel
"""


import mistune
from flask import Flask, render_template_string, redirect, render_template, url_for, abort, request
from flask import _app_ctx_stack
import re
import sys
import os
import subprocess as sp
import logging as log
import datetime as dt
from tempfile import TemporaryDirectory, NamedTemporaryFile
import time
import sqlite3

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

# =========
# init
# =========

# topdir = "documents/"
dummydir = "./dummy/"
md = mistune.Markdown()
latex_re = re.compile(r'<pre><code class="(lang|language)-(latex|math)">(.+?)</code></pre>', re.DOTALL)

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

#
# permission set
#
"""
Document Access Permission?
public: for all user but not generator
private: non public, It owes But High permission User for example 'admin' and 'moderator'
locked: 'highuser' can connect this simple locked document.
---
forbidden: for 'admin' and 'moderator' 
security: for 'admin' only

for example an example document perm is 'public/locked/security'
"""

doc_permission = {"public": 0, "private": 1, "locked": 2, "forbidden": 3, "security": 4}
private_permission = 1
public_document_permissions = [0, 1, 2]
"""
user permission?
banned: It was a human.
human: It is normal user
highuser: high user is allowed to connect locked document
moderator: sub admin
admin: admin!
"""

user_permission= {"banned": 0, "human": 1, "highuser": 2, "moderator": 3, "admin": 4}
generate_private_permission = 1






#
# sqlite db init
#

conn = None
curs = None

db_name = "docs.db"

conn = sqlite3.connect(db_name)
curs = conn.cursor()
# TODO: access_perm update to (get_perm, edit_perm, del_perm)
curs.execute("CREATE TABLE if not exists document (user, dir, doc_name, raw, compiled, last, access_perm)")
curs.execute("CREATE TABLE if not exists history (number, user, dir, doc_name, edit_user, ip, cause, length, type)")
curs.execute("CREATE TABLE if not exists user (name, id, pw, permission, date)")
conn.close()

conn = None
curs = None

def opendb(func):
    def wrapper(*args, **kwargs):
        global conn, curs
        conn = get_db()
        curs = conn.cursor()
        func(*args, **kwargs)
    return wrapper


### flask init
app = Flask(__name__)


def get_db():
    top = _app_ctx_stack.top
    if not hasattr(top, 'sqlite_db'):
        top.sqlite_db = sqlite3.connect(db_name)
    return top.sqlite_db


@app.teardown_appcontext
def close_connection(exception):
    top = _app_ctx_stack.top
    if hasattr(top, 'sqlite_db'):
        top.sqlite_db.close()




### define default functions
def composePath(*args:str):
    return "/".join([j for p in args
                    for i in p.split("/")
                    for j in i.split("\\")
                     if j]
                    )

def formatDatetime(datetime:dt.datetime):
    return datetime.strftime("%Y-%m-%d-%H:%M:%S")

def reformatDatetime(fdatetime:str):
    return dt.datetime.strptime(fdatetime, "%Y-%m-%d-%H:%M:%S")

def formatDatetimeNow():
    return formatDatetime(dt.datetime.now())

app.jinja_env.globals.update(composePath=composePath)



# =========
# define sqlite operation functions
# ========

#
# user
#
@opendb
def check_user_overlap(name:str, id:str):
    """
    :param name:
    :param id:
    :return: True if Exists Others else False
    check if exists same name or id
    """
    curs.execute("SELECT name, id FROM user WHERE name = :name OR id = :id", {"name": name, "id": id})
    return bool(curs.fetchall())


@opendb
def get_user_by_name(name):
    curs.execute("SELECT * FROM user WHERE name = :name", {"name": name})
    return curs.fetchone()

@opendb
def get_user_by_id(id):
    curs.execute("SELECT * FROM user WHERE id = :id", {"id": id})
    return curs.fetchone()

@opendb
def make_user(name:str, id:str, pw:str, perm:str = None):
    """
    :param name:
    :param id:
    :param pw:
    :param perm:
    :return: False if Can't make else True
    """

    if check_user_overlap(name, id):
        return False
    else:
        curs.execute("INSERT INTO user VALUES (:name, :id, :pw, :perm, :date)",
                     {'name': name, 'id': id, 'pw': pw, 'perm': perm, 'date': formatDatetimeNow()}
                     )
        conn.commit()
        curs.execute("INSERT INTO document VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (name, "", "→dir", None, None, formatDatetimeNow(), None)
                     )
        conn.commit()
        return True


#
# document
#


@opendb
def get_raw(user:str, dir:str, doc_name:str, acperm):
    curs.execute("SELECT raw FROM document WHERE user = ? AND dir = ? AND doc_name = ?", (user, dir, doc_name))
    return curs.fetchone()


@opendb
def get_compiled(user, dir, doc_name, acperm):
    curs.execute("SELECT compiled FROM document WHERE user = ? AND dir = ? AND doc_name = ?", (user, dir, doc_name))
    return curs.fetchone()




#
# path
#

@opendb
def get_dirs(user):
    curs.execute("SELECT user, dir FROM document WHERE user = ? AND doc_name='→dir'", {"user"})
    return curs.fetchall()

@opendb
def get_dirs_walk(user, dir):
    if dir == "":
        curs.execute("SELECT user, dir FROM document WHERE user = :user AND dir REGEXP '[^/]+ AND doc_name = '→dir'",
                     {"user": user}
                     )
    else:
        curs.execute("SELECT user, dir FROM document WHERE user = :user AND dir REGEXP :dir AND doc_name = '→dir'",
                     {"user": user, "dir": dir + r'/[^/]+'}
                     )
    return curs.fetchall()

@opendb
def get_documents(user):
    curs.execute("SELECT user, dir, doc_name FROM document WHERE user = :user AND doc_name <> '→dir'",
                 {"user": user}
                 )
    return curs.fetchall()

def get_documents_walk(user, dir):
    curs.execute("SELECT user, dir, doc_name FROM document WHERE user = :user AND dir = :dir AND doc_name <> '→dir'",
                 {"user": user, "dir": dir}
                 )
    return curs.fetchall()


#
# Make Dir Part
#

@opendb
def check_dir(user, dir, dir_name):
    curs.execute("SELECT dir FROM document WHERE user = :user AND dir = :dir AND doc_name='→dir'",
                 {"user": user, "dir": composePath(dir, dir_name)}
                 )
    t1 = curs.fetchall()  # It must not exist
    curs.execute("SELECT dir FROM document WHERE user = :user AND dir = :dir AND doc_name='→dir'",
                 {"user": user, "dir": dir}
                 )
    t2 = curs.fetchall()  # It must exist
    return not(bool(t1) is False and bool(t2) is True)

@opendb
def make_dir(user, dir, dir_name):
    if check_dir(user, dir, dir_name):
        return False
    else:

        curs.execute("INSERT INTO document VALUES (?, ?, ?, ?, ?, ?, ?)", (
            user, composePath(dir, dir_name), "→dir", None, None, formatDatetimeNow(), None)
                     )
        conn.commit()
        return True




@opendb
def del_all_document():
    try:
        curs.execute("DELETE FROM document")
        conn.commit()
    except Exception as e:
        print(e)





# =========
# Define Compile Functions
# ==========
def GFM_LMX(raw, extended = True, perm = True):
    lastendpos = 0


    output = md(raw)


    while 1:

        n = 0
        t = latex_re.search(output, lastendpos)
        if t:

            with TemporaryDirectory(prefix="tmpdir-", dir=dummydir) as tmpdir:
                with NamedTemporaryFile("w", encoding="utf-8", prefix="tmp-", suffix=".tex", dir=tmpdir, delete= False) as tmpf:
                    with open(tmpf.name, 'w', encoding='utf-8') as f:
                        f.write(LATEX_Cs % t.group(3))
                    op = sp.call(
                        "xelatex --no-pdf --output-directory={0} -interaction=nonstopmode --halt-on-error {1}".format(tmpdir, tmpf.name),
                        stdout=NamedTemporaryFile('w', encoding='utf-8', dir=tmpdir, delete=False)
                    )

                    if op == 1:
                        print("XeLaTeX 는 이상한 것이 분명하오 요카지마.")

                    else:
                        tempdvifname = os.path.splitext(tmpf.name)[0] + ".xdv"

                        op2: str = sp.check_output(
                            "dvisvgm --clipjoin -e --stdout --no-fonts {0}".format(tempdvifname),
                        )

                        output = latex_re.sub(op2.decode("utf-8"), output, count=1)


            lastendpos = t.end()
            n += 1
        else:
            break
    return output


def compile(user, dir, doc_name):
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
def c():
    print(get_user_by_id("354"))
    return ""

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
    """
    initial setting 해야함
    """
    app.run(host="localhost", port="54321",)
    print(get_user_by_id("354"))
    #print(get_raw('yenru0', '', 'teset'))
    #compile_all()
    #app.run(host="localhost", port="54321",)
    #mainWindow()