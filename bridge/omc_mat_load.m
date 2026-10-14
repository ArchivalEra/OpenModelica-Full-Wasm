%% omc-mat-load — 把 OpenModelica 仿真结果 (.mat, MAT4) 读成 Octave 变量
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 用法：
%%   r = omc_mat_load('/tmp/BouncingBall_res.mat');   % 读 + 建变量，返回元信息结构
%%   [r, S] = omc_mat_load(...);                      % S = 原始 struct（不该动它）
%%
%% 为什么需要它（需求 D 的实质，实测得出）：
%%   Octave 的 `load` **认** OpenModelica 的 MAT4 格式（`load` 返回 struct，字段名就是
%%   OM 的原始矩阵名 `Aclass`/`name`/`description`/`dataInfo`/`data_1`/`data_2`），
%%   但**不认它的语义** —— OpenModelica 的约定是
%%     · `name` 矩阵：mrows×ncols 的 char，**每列一个变量名**（NUL 补齐）；
%%     · `data_2` 矩阵：每行一个变量的时间序列（第 1 行 = time）；
%%   而 MATLAB/Octave 的 `load` 只会把顶层矩阵名当变量名（于是得到 `data_2` 而不是 `h`）。
%%   ⇒ 这一层"语义映射"就是两个引擎的握手点（`docs/REQUIREMENTS.md` 需求 D 的 D1）。
%%
%% 变量名消毒（实测踩到）：OM 允许 `der(h)` / `h[1]` 这类名字，而 Octave 的标识符
%%   只允许 `[A-Za-z_][A-Za-z0-9_]*` ⇒ 直接 `assignin` 会报
%%   `invalid variable name 'der(h)'`（**整条链断在这**，本函数第一版就是这么红的）。
%%   规则（可预期、可逆、不撞车）：
%%     · 非法字符（`()`/`[]`/`.`/` ` 等）→ `_`
%%     · 例：`der(h)` → `der_h_`；`h[1]` → `h_1_`；原名一并留在返回结构里可查。
%%     · 撞名（消毒后重复）→ 后缀 `_2`、`_3`…，并在 meta.renamed 里记原始名。
%%
%% 入口形式（`omc_mat_load_mat`）：接受"已经 load 出的 struct"或文件路径。

function [meta, raw] = omc_mat_load(file)
  if (nargin < 1 || isempty(file))
    error('omc_mat_load: 需要一个 .mat 文件路径');
  end
  if (isstruct(file))
    raw = file;  path = '(struct)';
  else
    path = file;
    if (exist(path, 'file') != 2)
      error('omc_mat_load: 文件不存在：%s', path);
    end
    raw = load(path);
  end

  % ── 认格式：OpenModelica 的 MAT4 必须带 name + data_2（缺一不可）────────────
  if (!isfield(raw, 'name') || !isfield(raw, 'data_2'))
    error(['omc_mat_load: 不是 OpenModelica 结果文件（缺 name / data_2 矩阵）。' ...
           'MATLAB 的 load 能读它，但语义映射需要这两个矩阵；' ...
           '若是别的 .mat（MATLAB v4/v7），请直接用 load。']);
  end

  N = raw.name;
  [mr, nc] = size(N);
  names = cell(1, nc);
  for k = 1:nc
    row = N(:, k)';
    z = find(row == 0, 1);
    if (isempty(z)), z = numel(row) + 1; end
    names{k} = row(1:z-1);
  end

  % ── 数据位置（★ 关键：不是每个变量都在 data_2 里）─────────────────────────
  % OpenModelica 按 `dataInfo` 矩阵分派（出处：上游
  % `openmodelica_mat_writer/src/lib.rs` 的 `Mat4Stream`：per signal `[channel, index,
  % interp, extrap]`）：
  %   channel = 2 ⇒ 随时间的量，值在 **data_2 的第 `index` 行**（index 从 1 起）；
  %   channel = 1 ⇒ 常数量（compile-time constant / 参数），值在 **data_1**（`index` 同理）。
  % 实测（本仓 2026-10-14，BouncingBall）：name 有 7 个（time/h/v/der(h)/der(v)/e/g），
  % 而 data_2 只有 5 行 —— `e`/`g` 是参数，落在 data_1。**第一版按"行数≥变量数"写，
  % 就直接报"文件损坏"**（假红，是判据错不是文件坏）。
  D = raw.data_2;
  [dr, dc] = size(D);
  has_info = isfield(raw, 'dataInfo');
  if (has_info)
    II = raw.dataInfo;   % 4 x nvars：[channel, index, interp, extrap]
    if (columns(II) < nc)
      error('omc_mat_load: dataInfo 列数(%d) < 变量数(%d)', columns(II), nc);
    end
  end
  D1 = [];
  if (isfield(raw, 'data_1')), D1 = raw.data_1; end

  % ── 消毒 + 建变量 ────────────────────────────────────────────────────────
  used = struct(); assigned = {}; renamed = {}; skipped = {}; kinds = {};
  for k = 1:nc
    orig = names{k};
    v = omc_mat_load_sanitize(orig);
    if (isempty(v))
      skipped{end+1} = orig;  continue;
    end
    base = v; n = 1;
    while (isfield(used, v) || omc_mat_load_is_builtin(v))
      n = n + 1; v = sprintf('%s_%d', base, n);
    end
    used.(v) = 1;
    if (!strcmp(v, orig)), renamed{end+1} = {orig, v}; end
    % 按 dataInfo 取值（缺 dataInfo ⇒ 退回旧行为：整行 data_2，写在下面兜底）
    if (has_info)
      ch = II(1, k); idx = II(2, k);
      if (ch == 0)
        % ★ channel 0 = **独立变量 time**（上游 `MatKind::Time` 的注释逐字：
        %   "The independent variable (`time`): data_2 row 1."）。
        %   它的 index 字段不可靠地当"行号"用（实测 idx=1，正好也是 data_2 第 1 行，
        %   但语义上是"独立变量"这个**类别**）⇒ 按语义取 data_2 第 1 行。
        %   （第一版只认 ch=1/2，于是 time 落进 else 被跳过 —— 自证台 ① 抓到。）
        if (dr < 1)
          error('omc_mat_load: 有独立变量 time 但 data_2 是空的');
        end
        val = D(1, :);  kind = 'time';
      elseif (ch == 2)
        if (idx < 1 || idx > dr)
          error('omc_mat_load: 变量 %s 指向 data_2 第 %d 行，但只有 %d 行', orig, idx, dr);
        end
        val = D(idx, :);
        kind = 'timeseries';
      elseif (ch == 1)
        if (isempty(D1) || idx < 1 || idx > numel(D1))
          error('omc_mat_load: 变量 %s 指向 data_1 第 %d 项，但 data_1 只有 %d 项', orig, idx, numel(D1));
        end
        val = D1(idx);          % 常量/参数：标量
        kind = 'constant';
      else
        skipped{end+1} = orig;  continue;    % 未知 channel ⇒ 明说不赋（不猜）
      end
    else
      if (k > dr)
        error('omc_mat_load: 缺 dataInfo 且 data_2 行数(%d) < 变量数(%d)', dr, nc);
      end
      val = D(k, :);  kind = 'timeseries(no-dataInfo)';
    end
    assignin('base', v, val);
    assigned{end+1} = v;  kinds{end+1} = kind;
  end

  meta = struct();
  meta.file = path;
  meta.format = 'OpenModelica MAT4';
  meta.names = names;
  meta.vars = assigned;
  meta.kinds = kinds;
  meta.renamed = renamed;
  meta.skipped = skipped;
  meta.samples = dc;
  meta.time = D(1, :);
  if (nargout < 2), raw = []; end
end

%% 与 Octave 内建函数撞名的变量（实测踩到）：`time` 就是最典型的 ——
%%   assignin 会把变量建出来，但调用 `time(1)` 会走**内建**的墙钟 `time()` 并报
%%   `Invalid call to time`。⇒ 名字撞内建时**主动改名**（`time` → `time_2`），
%%   并在 meta.renamed 里记下（读者能查）。这不是"绕开问题"：符号解析的优先级是
%%   Octave 的语义，我们只能按它的规则命名（且必须**可见地**改名）。
function tf = omc_mat_load_is_builtin(name)
  tf = false;
  % 只查"会被同名变量遮蔽后仍然抢戏"的那类：内建函数（exist 返回 5）
  if (exist(name) == 5), tf = true; end
end

%% 名字消毒（纯函数；自证走这里）
function v = omc_mat_load_sanitize(name)
  v = name;
  v(v == '(' | v == ')' | v == '[' | v == ']' | v == '{' | v == '}' | ...
    v == '.' | v == ',' | v == ' ' | v == ':' | v == ';' | v == '-' | v == '+') = '_';
  if (isempty(v)), return; end
  % 首字符必须是字母或下划线（数字开头 ⇒ 加前缀）
  if (!(isletter(v(1)) || v(1) == '_'))
    v = ['v_' v];
  end
end
