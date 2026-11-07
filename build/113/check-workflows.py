#!/usr/bin/env python3
"""OpenModelica-Full-Wasm — **workflow 语法闸门**（GitHub Actions 的 `run:` 块逐块 bash -n）

为什么需要（2026-11-02 实测踩到）：我在 `release.yml` 里插入新步骤时，把上一步的
`fi` 与 `echo out=` **甩到了末尾**（替换锚点匹配错），YAML 本身完全合法、`yaml.safe_load`
也通过，但 CI 跑到那一步才报 `syntax error near unexpected token 'fi'`。
⇒ **YAML 有效性 ≠ shell 有效性**。本闸门把每个 `run:` 块抽出来跑 `bash -n`（只解析不执行），
在提交前就抓住这类错误。

判据：
  ① 每个 `run:` 块 `bash -n` 通过（含 heredoc 的，原文照跑）
  ② workflow 能被 YAML 解析
  ③ 每个 job 至少有一个 step（零值守卫：空 job 不是通过）
  ④ `${{ }}` 表达式配对（漏写 `}}` 是常见手误）

用法：python3 build/113/check-workflows.py [--selftest] [--dir .github/workflows]
退出码：0 = 全过；1 = 有问题；2 = 环境
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WF_DIR = os.path.join(REPO, ".github", "workflows")


def _bash_syntax_ok(script):
    """`bash -n` 只做语法解析，不执行 —— 安全，且能抓出 `fi` 错位这类问题。"""
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as fh:
        # 把 GitHub 的 `${{ }}` 表达式替换成无害占位（bash 不认 `{{` 里的内容）
        fh.write(re.sub(r"\$\{\{[^}]*\}\}", "EXPR", script))
        path = fh.name
    try:
        r = subprocess.run(["bash", "-n", path], capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stderr or "").strip()[:300]
    finally:
        os.unlink(path)


def _unbalanced_expr(script):
    """`${{` 与 `}}` 数量不等 ⇒ 手误（常见：`${{ inputs.x }`）。"""
    return script.count("${{") != script.count("}}")


def check_workflows(dwf, run_bash=True):
    """返回问题列表（空即全过）。

    三步：目录前置检查 → 逐文件 YAML/形状 → 逐 run 块 bash -n。
    """
    probs = []
    if not os.path.isdir(dwf):
        return ["workflow 目录不存在：%s（环境问题）" % dwf]
    files = sorted(f for f in os.listdir(dwf) if f.endswith((".yml", ".yaml")))
    if not files:
        return ["workflow 目录里没有任何 yml（零值守卫：空目录不是通过）"]
    try:
        import yaml
    except ImportError:
        return ["缺 pyyaml（环境问题，不是通过）"]
    for fn in files:
        probs += _check_one_workflow(os.path.join(dwf, fn), fn, run_bash)
    return probs


def _check_one_workflow(path, fn, run_bash):
    """单文件：YAML 可解析 → 有 jobs → 每个 job 有 steps → 每个 run 块过 bash -n。"""
    probs = []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        doc = yaml_safe(text)
    except Exception as e:
        return ["%s: YAML 解析失败：%r" % (fn, e)]
    if not isinstance(doc, dict) or not doc.get("jobs"):
        return ["%s: 没有 jobs（空 workflow 不是通过）" % fn]
    for job_name, job in (doc.get("jobs") or {}).items():
        steps = (job or {}).get("steps") or []
        if not steps:
            probs.append("%s/%s: 没有 steps（零值守卫）" % (fn, job_name))
        for i, st in enumerate(steps):
            probs += _check_step("%s/%s/step#%d(%s)" % (fn, job_name, i, st.get("name", "?")),
                                 st, run_bash)
    return probs


def yaml_safe(text):
    import yaml
    return yaml.safe_load(text)


def _check_step(label, step, run_bash):
    """单个 step：表达式配对 + （可选）bash -n。"""
    script = step.get("run")
    if script is None:
        return []                     # uses: 步骤没有 run
    probs = []
    if _unbalanced_expr(script):
        probs.append("%s: `${{ }}` 配对数不等" % label)
    if run_bash:
        ok, err = _bash_syntax_ok(script)
        if not ok:
            probs.append("%s: bash -n 失败：%s" % (label, err))
    return probs


def selftest():
    """三类用例：正常不报 / 该报的必须报 / 空输入必须报。"""
    fails, ok = [], [0]

    def chk(name, cond, detail=""):
        if cond:
            ok[0] += 1
            print("ok   %s" % name)
        else:
            fails.append(name)
            print("FAIL %s%s" % (name, ("  [" + detail + "]") if detail else ""))

    # ① 正常
    good = """if true; then
  echo a
fi
echo done
"""
    o, err = _bash_syntax_ok(good)
    chk("正常 shell ⇒ bash -n 过", o, err)

    # ② 该报的必须报（★ 就是我在 release.yml 里犯的那个错：fi 悬在末尾）
    bad = """if true; then
  echo a
fi
echo x
PY
fi
echo "out=$OUT"
"""
    o2, err2 = _bash_syntax_ok(bad)
    chk("★ 多余 fi（我犯过的形状）⇒ bash -n 必须报", not o2, err2)
    chk("★ `${{ inputs.x }` 漏一个 } ⇒ 必须报", _unbalanced_expr("run: echo ${{ inputs.x }"))
    chk("正常 `${{ inputs.x }}` ⇒ 不报", not _unbalanced_expr("echo ${{ inputs.x }}"))

    # ③ 空输入必须报
    chk("★ 空目录 ⇒ 必须报", check_workflows("/nonexistent/wf") != [])
    empty = tempfile.mkdtemp()
    chk("★ 目录里无 yml ⇒ 必须报", check_workflows(empty) != [])

    print("=== %d PASS / %d fail ===" % (ok[0], len(fails)))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=WF_DIR)
    ap.add_argument("--no-bash", action="store_true", help="只查 YAML 与表达式配对")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    probs = check_workflows(a.dir, run_bash=not a.no_bash)
    if probs:
        print("workflow 检查：%d 个问题" % len(probs))
        for p in probs:
            print("  · %s" % p)
        sys.exit(1)
    print("workflow 检查：OK（YAML + 每个 run 块 bash -n + 表达式配对）")
    sys.exit(0)


if __name__ == "__main__":
    main()
