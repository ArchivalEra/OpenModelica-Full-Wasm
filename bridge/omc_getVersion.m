%% omc_getVersion — 读 OpenModelica 的版本串（MATLAB 语义桥的第一件，需求 E）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 用法： v = omc_getVersion()        % 返回字符串
%%
%% ── 为什么是这个形状（需求 E1 的"命令驱动"，实测决定）─────────────────────
%% 本 build 里 Octave 与 omc 是**两个独立的 wasm**，中间隔着浏览器。`.m` 代码能触达宿主
%% 的通道只有两族（`bridge/queue.js` 的注释逐字记着）：
%%   · **MEMFS 文件队列**：`.m` 追加一行请求 → 宿主读走并清空 → 宿主把结果写回文件；
%%   · `__web_fetch_sync__`（sync XHR）—— 但实测 **sync XHR 不被 Service Worker 拦截**，
%%     所以它只能取"服务端真有"的 URL，不能取"宿主现算"的字节。
%% ⇒ `omc_getVersion`/`omc_simulate` 走**文件队列**（同族协议：请求一行 + 结果文件），
%%   由宿主（页面或 Node 测试）负责把请求转给 omc 并把结果写回。
%% 这与 OMMatlab 的 `sendExpression` 是**同一协议、不同传输层**（需求书 §1.5 原文）。
%%
%% 队列协议（本文件定义，宿主侧实现见 bridge/omc_bridge.js）：
%%   /tmp/omc_req.txt   一行一条请求：`<seq>\t<command>`
%%   /tmp/omc_res.txt   一行一条应答：`<seq>\t<ok|err>\t<payload>`
%%   payload 里的换行/制表符转义（见 omc_bridge.js 的 codec）

function v = omc_getVersion()
  r = omc_call_internal('getVersion()');
  if (!r.ok)
    error('omc_getVersion: %s', r.err);
  end
  % omc 回的是带引号的 Modelica 字符串（实测 `"-rust"`）⇒ 去掉引号
  v = r.text;
  v = regexprep(v, '^"', '');
  v = regexprep(v, '"$', '');
end
