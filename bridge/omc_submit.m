%% omc_submit — 提交一条 omc 命令（**不等待**），返回 seq（E 的异步两段式 API）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 为什么是两段式（2026-10-14 实测，血的教训）：
%%   · Octave（worker）里的**忙等会占住 worker 线程**，而宿主读 MEMFS 也得经过 worker
%%     ⇒ "Octave 等应答 + 宿主读请求"两边互等 ⇒ **死锁**（实测：Octave 忙 3s 时宿主
%%     evaluate 被阻塞 2701ms；worker 模式下同样成立，因为 worker 是单线程）。
%%   · ⇒ **`.m` 侧绝不等待**：提交请求后立刻返回；宿主完成后由宿主**再次调用** Octave
%%     （`omc_collect(seq)`）把结果取回。这样任何时刻只有一边在跑。
%%
%% 用法（宿主驱动）：
%%   seq = omc_submit('getVersion()')        ⇒ 请求已写进 /tmp/omc_req.txt，立即返回
%%   …宿主转给 omc 并把应答写进 /tmp/omc_res.txt…
%%   r = omc_collect(seq)                     ⇒ 取回 {ok, text, err}
function seq = omc_submit(command)
  REQ = '/tmp/omc_req.txt';
  seqFile = '/tmp/omc_seq.txt';
  seq = 1;
  if (exist(seqFile, 'file') == 2)
    s = fileread(seqFile);
    v = str2double(strtrim(s));
    if (!isnan(v)), seq = v + 1; end
  end
  f = fopen(seqFile, 'w'); fprintf(f, '%d', seq); fclose(f);
  f = fopen(REQ, 'a');
  if (f < 0)
    error('omc_submit: 打不开请求队列 %s（宿主桥没装？）', REQ);
  end
  fprintf(f, '%d\t%s\n', seq, command);
  fclose(f);
end
