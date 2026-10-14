%% omc_fs_read — 读 MEMFS 文件内容，**摘要 + 分块**回给宿主（E 的传输助手）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 用法（宿主侧）：`omc_fs_read('/tmp/x')`
%%   成功：`__OMCFS_BEGIN__ <nbytes>` … 每行 `__OMCFS_L <base64>` … `__OMCFS_END__`
%%   失败：`__OMCFS_MISSING__`
%%
%% ★ 为什么走 **base64 分块**（2026-10-14 实测踩过的三个坑）：
%%   ① 直接 `disp(文件内容)`：多行文本只在**第一行**带标记，宿主抓不齐；
%%   ② 逐字符转义（`strrep` 成 `\n` 字面量）：与 MATLAB/Octave 的转义语义纠缠
%%      （原文件里本来就可能有反斜杠）⇒ 不可逆；
%%   ③ `eval` 的返回值**不含求值结果**（worker 模式实测）⇒ 只能走 stdout。
%%   base64 是唯一"内容里任何字节都不会与通道标记冲突"的编码 ⇒ 分块 + base64。
function omc_fs_read(p)
  if (exist(p, 'file') != 2)
    disp('__OMCFS_MISSING__');
    return;
  end
  f = fopen(p, 'r');
  if (f < 0), disp('__OMCFS_MISSING__'); return; end
  bytes = fread(f, Inf, '*uint8')';
  fclose(f);
  b64 = base64_encode(bytes);
  CHUNK = 4000;                      % 每行字符数（够小，避免超长行）
  n = numel(b64);
  disp(sprintf('__OMCFS_BEGIN__ %d', numel(bytes)));
  k = 1;
  while (k <= n)
    e = min(k + CHUNK - 1, n);
    disp(['__OMCFS_L ' b64(k:e)]);
    k = e + 1;
  end
  disp('__OMCFS_END__');
end
