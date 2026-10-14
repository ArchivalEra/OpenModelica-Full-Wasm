%% omc_simulate — 在 omc 里仿真一个模型并把结果读成表格（需求 E2 的判据物）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 用法：
%%   r = omc_simulate('BouncingBall', 'stopTime', 3.0)
%%   r.time / r.data（每列一个变量）/ r.names（变量名 cell）/ r.samples
%%   r = omc_simulate(..., 'mo', 'path/to/Model.mo')   % 先 loadFile 再仿真
%%
%% 判据（需求 E2）：在 Octave 里 `omc_simulate('BouncingBall')` ⇒ **返回数据矩阵**。
%%
%% 实现要点（实测决定）：
%%   · omc 侧产出的是 **MAT4** 结果文件；把它取回本进程后，直接用**同仓的**
%%     `omc_mat_load`（需求 D 那个桥接函数）解析 —— 不重复实现 MAT4 读取。
%%   · 变量名 sanitize、`time`/`e` 撞内建改名等语义都归 `omc_mat_load` 管
%%     （它有自证台：test/browser/selftest-mat-bridge.sh）。

function r = omc_simulate(class_name, varargin)
  if (nargin < 1 || isempty(class_name))
    error('omc_simulate: 需要模型名');
  end
  opt.stopTime = 1.0;
  opt.mo = '';
  k = 1;
  while (k <= numel(varargin))
    switch (lower(varargin{k}))
      case 'stoptime', opt.stopTime = varargin{k+1}; k += 2;
      case 'mo',       opt.mo = varargin{k+1};       k += 2;
      otherwise, error('omc_simulate: 未知选项 %s', varargin{k});
    end
  end

  if (!isempty(opt.mo))
    rr = omc_call_internal(sprintf('loadFile("%s")', opt.mo));
    if (!rr.ok || !strcmp(strtrim(rr.text), 'true'))
      error('omc_simulate: loadFile 失败：%s', rr.err);
    end
  end

  % 仿真（omc 侧一口气跑完；宿主把结果 .mat 写回 VFS，本函数再读）
  rr = omc_call_internal(sprintf('simulate(%s, stopTime=%g)', class_name, opt.stopTime));
  if (!rr.ok)
    error('omc_simulate: 仿真失败：%s', rr.err);
  end
  % 结果文件路径由宿主在 payload 里给出（一行：`MAT <vfs路径>`）
  m = regexp(rr.text, 'MAT\s+(\S+)', 'tokens');
  if (isempty(m))
    error('omc_simulate: 应答里没有结果文件路径（宿主桥版本不符？）: %s', rr.text);
  end
  vfsPath = m{1}{1};

  % 取字节（宿主已把它写进本进程能读的路径 —— 同一 wasm 的 MEMFS）
  if (exist(vfsPath, 'file') != 2)
    error('omc_simulate: 结果文件不在 %s（宿主没写进来？）', vfsPath);
  end

  % 复用需求 D 的桥接函数（它在 bridge/ 里，靠 addpath 可见）
  meta = omc_mat_load(vfsPath);
  r = struct();
  r.names = meta.vars;
  r.samples = meta.samples;
  r.time = meta.time;
  r.data = zeros(numel(meta.vars), meta.samples);
  for i = 1:numel(meta.vars)
    r.data(i, :) = evalin('base', meta.vars{i});
  end
  r.meta = meta;
end
