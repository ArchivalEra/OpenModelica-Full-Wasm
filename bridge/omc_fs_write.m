%% omc_fs_write — 把宿主给的字节写进 MEMFS（E 的传输助手）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 用法（宿主侧）：`omc_fs_write('/tmp/x.mat', [1 2 3 ...])`   % 数值数组 = 字节值
%%   —— 写成功 disp `__OMCFS_WROTE__ <n>`。
function omc_fs_write(p, bytes)
  f = fopen(p, 'w');
  if (f < 0)
    disp('__OMCFS_FAIL__');
    return;
  end
  fwrite(f, uint8(bytes));
  fclose(f);
  disp(sprintf('__OMCFS_WROTE__ %d', numel(bytes)));
end
