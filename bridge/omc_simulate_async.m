%% omc_simulate_async — 两段式仿真：提交（不等待）⇒ 宿主转给 omc ⇒ 取回结果路径
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 用法（宿主驱动，见 test/browser/accept-omc-bridge.mjs）：
%%   [seq, kind] = omc_simulate_async('BouncingBall', 'stopTime', 3.0, 'mo', '/x.mo')
%%     kind = 'load'|'simulate'  —— 宿主据此决定这一条要干什么
%%   r = omc_collect(seq)        —— 取回；simulate 那步的 payload 是 `MAT <vfs路径>`
%%
%% 为什么拆两段：见 omc_submit 的头注（忙等会死锁）。
function [seq, kind, payload] = omc_simulate_async(class_name, varargin)
  opt.stopTime = 1.0; opt.mo = '';
  k = 1;
  while (k <= numel(varargin))
    switch (lower(varargin{k}))
      case 'stoptime', opt.stopTime = varargin{k+1}; k += 2;
      case 'mo',       opt.mo = varargin{k+1};       k += 2;
      otherwise, error('omc_simulate_async: 未知选项 %s', varargin{k});
    end
  end
  if (!isempty(opt.mo))
    seq = omc_submit(sprintf('loadFile("%s")', opt.mo));
    kind = 'load'; payload = opt.mo;
    return;
  end
  seq = omc_submit(sprintf('simulate(%s, stopTime=%g)', class_name, opt.stopTime));
  kind = 'simulate'; payload = class_name;
end
