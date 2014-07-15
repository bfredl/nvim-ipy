" TODO: make configuarble
nnoremap <F5> :call send_event(0, "ipy_run",['line'])<cr>
vnoremap <F5> :<c-u>call send_event(0, "ipy_run",['visual'])<cr>
inoremap <C-Space> <c-o>:<c-u>call send_event(0, "ipy_complete",[])<cr>

map <Plug>ch:un <F5>
imap <Plug>ch:eu <C-Space>

