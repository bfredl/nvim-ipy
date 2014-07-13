function! Ipy_runline()
    call send_event(0, "ipy_runline",[])
endfunction

" TODO: generally sane defaults...
noremap ä :call Ipy_runline()<cr>
inoremap <Plug>ch:eu <c-o>:<c-u>call send_event(0, "ipy_complete",[])<cr>


