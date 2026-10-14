%% omc_collect — 取回 `omc_submit` 提交的那条命令的应答（**不等待**：没有就明说还没有）
%% SPDX-License-Identifier: AGPL-3.0-or-later
%%
%% 返回 struct： .ok（逻辑） .text（payload） .err（错误文本） .pending（逻辑：还没有应答）
function r = omc_collect(seq)
  RES = '/tmp/omc_res.txt';
  r = struct('ok', false, 'text', '', 'err', '', 'pending', true);
  if (exist(RES, 'file') != 2)
    return;   % 还没有（宿主没写）
  end
  lines = strsplit(fileread(RES), "\n");
  for k = 1:numel(lines)
    ln = lines{k};
    if (isempty(ln)), continue; end
    parts = strsplit(ln, "\t");
    if (numel(parts) >= 2 && str2double(parts{1}) == seq)
      r.pending = false;
      r.ok = strcmp(parts{2}, 'ok');
      payload = '';
      if (numel(parts) >= 3), payload = omc_unescape_internal(parts{3}); end
      if (r.ok), r.text = payload; else r.err = payload; end
      return;
    end
  end
end

%% 反转义（与 JS 侧 escape 对称）
function s = omc_unescape_internal(s)
  s = strrep(s, '\\n', "\n");
  s = strrep(s, '\\t', "\t");
  s = strrep(s, '\\\\', '\\');
end
