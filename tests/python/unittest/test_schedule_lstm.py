import tvm

def test_lstm_cell_inline():
    num_step = 128
    num_input = 256
    num_hidden = 1152
    batch_size = 4
    # Global transition matrix
    X = tvm.placeholder((num_step - 1, batch_size, num_input), name="X")
    Wi2h = tvm.placeholder((4, num_hidden, num_input), name="Wi2h")
    Wh2h = tvm.placeholder((4, num_hidden, num_hidden), name="Wh2h")
    # h: output hidden state, c: cell state.
    s_state_h = tvm.placeholder((num_step, batch_size, num_hidden))
    s_state_c = tvm.placeholder((num_step, batch_size, num_hidden))
    s_init_c = tvm.compute((1, batch_size, num_hidden),
                           lambda *i: 0.0, name="init_c")
    s_init_h = tvm.compute((1, batch_size, num_hidden),
                           lambda *i: 0.0, name="init_h")
    # LSTM transition
    k = tvm.reduce_axis((0, num_input), name="ki2h")
    s_i2h = tvm.compute(
        (num_step, 4, batch_size, num_hidden),
        lambda t, x, i, j: tvm.sum(X[t - 1, i, k] * Wi2h[x, j, k], axis=k),
        name="s_i2h")
    k = tvm.reduce_axis((0, num_hidden), name="ki2h")
    s_h2h = tvm.compute(
        (num_step, 4, batch_size, num_hidden),
        lambda t, x, i, j: tvm.sum(s_state_h[t - 1, i, k] * Wh2h[x, j, k], axis=k),
        name="s_h2h")
    # Gate rules
    gates = tvm.compute(s_i2h.shape, lambda *i:
                        s_i2h(*i) + s_h2h(*i), name="gates")
    gshape = (num_step, batch_size, num_hidden)
    in_gate = tvm.compute(gshape, lambda t, i, j: tvm.sigmoid(gates[t, 0, i, j]), name="in_gate")
    in_transform = tvm.compute(gshape, lambda t, i, j: tvm.tanh(gates[t, 1, i, j]), name="in_transform")
    forget_gate = tvm.compute(gshape, lambda t, i, j: tvm.sigmoid(gates[t, 2, i, j]), name="forget_gate")
    out_gate = tvm.compute(gshape, lambda t, i, j: tvm.sigmoid(gates[t, 3, i, j]), name="out_gate")
    next_c = tvm.compute(gshape,
                         lambda t, i, j:
                         forget_gate[t, i, j] * s_state_c[t - 1, i, j] +
                         in_gate[t, i, j] * in_transform[t, i, j], name="next_c")
    next_h = tvm.compute(gshape,
                         lambda t, i, j: out_gate[t, i, j] * tvm.tanh(next_c[t, i, j]), name="next_h")
    update_c = tvm.compute(gshape, lambda *i: next_c(*i), name="update_c")
    update_h = tvm.compute(gshape, lambda *i: next_h(*i), name="update_h")
    # schedule
    scan_h, scan_c = tvm.scan(
        [s_init_h, s_init_c],
        [update_h, update_c],
        [s_state_h, s_state_c],
        inputs=[X],
        name="lstm_scan")
    # schedule
    s = tvm.create_schedule(scan_h.op)
    # Inline gate computations
    s[gates].compute_inline()
    s[in_gate].compute_inline()
    s[in_transform].compute_inline()
    s[forget_gate].compute_inline()
    s[out_gate].compute_inline()
    # verify we can lower correctly
    tvm.lower(s, [X, Wi2h, Wh2h, scan_h, scan_c], with_api_wrapper=False)

if __name__ == "__main__":
    test_lstm_cell_inline()