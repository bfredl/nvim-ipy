local function append_outbuf(text)
  vim.api.nvim_command("echoerr '"..text.."'")
end

return {append_outbuf=append_outbuf}
