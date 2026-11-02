"""Decode C1 condition blobs and compare their AST to paired source expressions."""
import re
import struct

BINARY = {0: '&&', 1: '||', 2: '<', 3: '<=', 4: '>', 5: '>=', 6: '==', 7: '!='}


def read_condition(data):
    if len(data) < 8 or data[:2] != b'C1':
        raise ValueError('not a C1 condition')
    size = struct.unpack_from('<H', data, 2)[0]
    root = data[4]
    nv = data[6]
    if size != len(data) or root != ((7 + nv + 3) & ~3):
        raise ValueError('C1 size or root alignment mismatch')
    variables = list(data[7:7 + nv])
    visited, active, literal_offsets, instructions = {}, set(), set(), []
    def node(index):
        if index in visited:
            return visited[index]
        if index in active:
            raise ValueError('cyclic C1 expression')
        active.add(index)
        off = root + index * 4
        if off < root or off + 4 > len(data):
            raise ValueError('C1 node out of bounds')
        op, a, child_b, reserved = struct.unpack_from('<BBBB', data, off)
        b = struct.unpack_from('<H', data, off + 2)[0]
        instructions.append({'index': index, 'offset': off, 'opcode': op, 'byte1': a, 'u16_at_2': b})
        if op in BINARY:
            value = [BINARY[op], node(a), node(child_b)]
        elif op in (8, 9):
            if b not in variables:
                raise ValueError('C1 variable absent from header')
            value = ['var' if op == 9 else 'local_var', b]
        elif op == 11:
            pos = off + b
            if pos + 4 > len(data):
                raise ValueError('C1 literal out of bounds')
            value = ['number', struct.unpack_from('<f', data, pos)[0]]
            literal_offsets.add(pos)
        else:
            raise ValueError(f'unmapped C1 opcode {op} at {off:#x}')
        active.remove(index)
        visited[index] = value
        return value
    ast = node(0)
    if literal_offsets and min(literal_offsets) < root + (max(visited) + 1) * 4:
        raise ValueError('C1 literals overlap reachable instructions')
    return {'variables': variables, 'root_offset': root, 'node_count': len(visited),
            'literal_offsets': sorted(literal_offsets), 'ast': ast,
            'instructions': sorted(instructions, key=lambda x: x['index'])}


TOKEN = re.compile(r'\s*(\$\d+|\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||[()!<>+\-])')


def parse_text(text):
    tokens, pos = [], 0
    while pos < len(text.rstrip()):
        m = TOKEN.match(text, pos)
        if not m:
            raise ValueError('unmapped text token at ' + text[pos:])
        tokens.append(m[1])
        pos = m.end()
    i = 0
    precedence = {'||': 1, '&&': 2, '==': 3, '!=': 3, '<': 3, '>': 3, '<=': 3, '>=': 3}
    def expression(level=0):
        nonlocal i
        if i >= len(tokens):
            raise ValueError('missing operand')
        t = tokens[i]
        i += 1
        if t == '(':
            left = expression()
            if i >= len(tokens) or tokens[i] != ')':
                raise ValueError('missing closing parenthesis')
            i += 1
        elif t == '-':
            if i >= len(tokens):
                raise ValueError('missing negative literal')
            left = ['number', -float(tokens[i])]
            i += 1
        elif t.startswith('$'):
            left = ['var', int(t[1:])]
        else:
            left = ['number', float(t)]
        while i < len(tokens) and precedence.get(tokens[i], -1) >= level:
            op = tokens[i]
            i += 1
            right = expression(precedence[op] + 1)
            left = [op, left, right]
        return left
    result = expression()
    if i != len(tokens):
        raise ValueError('unconsumed text tokens')
    return result


def normalized(ast):
    op = ast[0]
    if op in ('var', 'number'):
        return ast
    children = []
    for child in ast[1:]:
        v = normalized(child)
        if op in ('&&', '||') and v[0] == op:
            children.extend(v[1:])
        else:
            children.append(v)
    return [op, *children]
