%% omc_fs_write_b64__ — 写 base64 文本到 MEMFS（E 的注入助手；避免逐字节转义）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%% 用法（宿主侧）：`omc_fs_write_b64__('/bridge/x.m', '<base64>')`
function omc_fs_write_b64__(p, b64)
  bytes = base64_decode(b64);
  f = fopen(p, 'w');
  if (f < 0), disp('__OMCFS_FAIL__'); return; end
  fwrite(f, uint8(bytes));
  fclose(f);
  disp(sprintf('__OMCFS_WROTE__ %d', numel(bytes)));
end
