function! Ipy_runline()
    call send_event(0, "ipy_runline",[])
endfunction

" because swedish
noremap ä :call Ipy_runline()<cr>


