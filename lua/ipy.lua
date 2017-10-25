local a = vim.api

local function update_outbuf(buf, expected_oldtext, lines, hls)
  local pos = a.nvim_buf_line_count(buf)-1
  local oldtext = a.nvim_buf_get_lines(buf,-2,-1,true)[1]
  -- TODO: eliminate this check by moving ANSI parsing lua side
  if expected_oldtext ~= oldtext then
    a.nvim_buf_set_lines(buf,-2,-1,true,{oldtext.."\r"})
    pos = pos +1
  end
  a.nvim_buf_set_lines(buf,pos,-1,true,lines)
  for _, hl in ipairs(hls) do
     a.nvim_buf_add_highlight(buf, 0, hl[1], pos+hl[2], hl[3], hl[4])
  end
end

x = update_outbuf

return {update_outbuf=update_outbuf}
