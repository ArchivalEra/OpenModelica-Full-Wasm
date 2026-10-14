%% omc_simulate_model — 需求 E2 的**判据物**：`omc_simulate_model('BouncingBall')` ⇒ 数据矩阵
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 与 `omc_simulate_async` 的分工：后者是**原语**（一次提交一步，宿主驱动）；
%% 本函数把"载模型 + 仿真 + 解析"串成**一条命令**（`simulateModel`），宿主一次做完。
%%
%% 用法：
%%   [seq, cls] = omc_simulate_model('BouncingBall', 'stopTime', 3.0)
%%     宿主：收到 seq 后调 omc 的 `simulateModel(Class, stopTime)`（含 loadFile），
%%           把结果 .mat 落地到 MEMFS，应答 `MAT <path>`；
%%   r = omc_collect(seq)   —— 取回 {ok,text,err}；text = `MAT <path>`
%%
%% 为什么合成一条（需求书 E2 原文是 `omc_simulate('BouncingBall')` 一步到位）：
%%   两步（loadFile 再 simulate）在**协议层**是同一件事，但合成一条更贴近判据原文、
%%   也少一次往返。模型源码的**位置约定**：宿主在 Octave 的 FS 里找 `~/<Class>.mo`
%%   或 `/tmp/<Class>.mo`（后者优先），找到就搬进 omc 的 VFS 并 loadFile。
function [seq, cls] = omc_simulate_model(class_name, varargin)
  if (nargin < 1 || isempty(class_name))
    error('omc_simulate_model: 需要模型名');
  end
  if (!ischar(class_name) || isempty(regexp(class_name, '^[A-Za-z_][A-Za-z0-9_.]*$', 'once')))
    error('omc_simulate_model: 模型名不合法：%s', class_name);
  end
  stopTime = 1.0;
  k = 1;
  while (k <= numel(varargin))
    switch (lower(varargin{k}))
      case 'stoptime', stopTime = varargin{k+1}; k += 2;
      otherwise, error('omc_simulate_model: 未知选项 %s', varargin{k});
    end
  end
  seq = omc_submit(sprintf('simulateModel(%s, stopTime=%g)', class_name, stopTime));
  cls = class_name;
end
