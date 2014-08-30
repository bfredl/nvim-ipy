nnoremap <Plug>(IPy-RunLine) :call send_event(0, "ipy_run",'line')<cr>
vnoremap <Plug>(IPy-RunLine) :<c-u>call send_event(0, "ipy_run",'visual')<cr>
inoremap <Plug>(IPy-Complete) <c-o>:<c-u>call send_event(0, "ipy_complete")<cr>
noremap <Plug>(IPy-Interrupt) :call send_event(0, "ipy_interrupt")<cr>

function! IPyRun(code)
    call send_event(0, "ipy_run", ['code', a:code])
endfunction

if !exists('g:nvim_ipy_perform_mappings')
    let g:nvim_ipy_perform_mappings = 1
endif

if g:nvim_ipy_perform_mappings
    map <silent> <F5>           <Plug>(IPy-RunLine)
    imap <silent> <C-Space> <Plug>(IPy-Complete)
    map <silent> <F8> <Plug>(IPy-Interrupt)
endif

