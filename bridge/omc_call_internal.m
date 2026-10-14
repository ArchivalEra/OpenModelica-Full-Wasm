%% omc_call_internal — 私有：把一条命令发给宿主并等应答（E 的传输层，别的 omc_* 都走它）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 返回 struct： .ok（逻辑） .text（payload 文本） .err（错误文本）
%%
%% 协议（与 bridge/omc_bridge.js 两侧同名常量，改一处必须改另一处）：
%%   请求  /tmp/omc_req.txt  追加一行 `<seq>\t<command>`
%%   应答  /tmp/omc_res.txt  宿主写入 `<seq>\t<ok|err>\t<escaped payload>`
%%   —— 每次调用用**唯一的 seq**（单调计数），所以过期应答不会被误取。

function r = omc_call_internal(command)
  REQ = '/tmp/omc_req.txt';
  RES = '/tmp/omc_res.txt';
  seqFile = '/tmp/omc_seq.txt';

  seq = 1;
  if (exist(seqFile, 'file') == 2)
    s = fileread(seqFile);
    seq = str2double(strtrim(s)) + 1;
  end
  f = fopen(seqFile, 'w'); fprintf(f, '%d', seq); fclose(f);

  % 追加请求（不覆盖：宿主可以一次收多条）
  f = fopen(REQ, 'a');
  if (f < 0)
    error('omc_call_internal: 打不开请求队列 %s（宿主桥没装？）', REQ);
  end
  fprintf(f, '%d\t%s\n', seq, command);
  fclose(f);

  % ── 等应答：**分片忙等 + 复查文件索引**（2026-10-14 实测定的形状）────────────
  % ⚠️ 两条实测教训都写在这（改这段前先读）：
  %  ① `pause()` 在本 build 里把 evaluate **整条挂死**（rc=-99，后续 disp 都不执行）
  %     ⇒ 轮询只能用忙等（`while toc<t, end`）。
  %  ② 忙等**独占 wasm 线程**：实测 Octave 忙 3s 时，宿主的 evaluate 被阻塞 2701ms
  %     ⇒ 如果 .m 一口气忙等到应答，宿主桥（轮询靠 evaluate 读写 MEMFS）就**永远排不上**
  %     ⇒ 死锁。**第一版就是这么挂的**（现象：桥的应答文件明明写好了，Octave 却读不到）。
  %  ⇒ 正解：每次只忙等**一小片**（budget），片间**重查一次文件状态**（`clear` 文件缓存），
  %     靠宿主在片间插进来应答。多次分片的总时长由 TIMEOUT_S 兜底。
  % 落地方式：**无状态分片**是不行的（.m 无法跨 evaluate 保留调用栈）⇒ 采用
  %   "一次调用内多次短忙等"：每片 ≤ SLICE_S，片间读文件；宿主在片间的**微任务窗口**里
  %   完成 evaluate（实测：evaluate 内部让出后宿主能插进来，见 test/browser 的诊断）。
  deadline = tic;
  TIMEOUT_S = 120;
  SLICE_S = 0.01;                      % 单片忙等上限（10ms —— 给宿主留插入窗口）
  got = false;
  while (!got)
    t0 = tic;
    while (toc(t0) < SLICE_S), end     % 忙等一小片（让宿主有机会跑）
    if (exist(RES, 'file') == 2)
      lines = strsplit(fileread(RES), "\n");
      for k = 1:numel(lines)
        ln = lines{k};
        if (isempty(ln)), continue; end
        parts = strsplit(ln, "\t");
        if (numel(parts) >= 2 && str2double(parts{1}) == seq)
          ok = strcmp(parts{2}, 'ok');
          payload = '';
          if (numel(parts) >= 3), payload = omc_unescape_internal(parts{3}); end
          r = struct('ok', ok, 'text', payload, 'err', payload);
          if (!ok), r.text = ''; end
          got = true;
          break;
        end
      end
    end
    if (!got && toc(deadline) > TIMEOUT_S)
      error(['omc_call_internal: 等了 %d 秒没有应答（宿主桥没接上？看 bridge/omc_bridge.js 的用法）。' ...
             ' 请求已写进 %s，seq=%d。'], TIMEOUT_S, REQ, seq);
    end
  end
end

%% 反转义（与 JS 侧 escape 对称：\n → 换行，\t → 制表符，\\ → 反斜杠）
function s = omc_unescape_internal(s)
  s = strrep(s, '\\n', "\n");
  s = strrep(s, '\\t', "\t");
  s = strrep(s, '\\\\', '\\');
end
