# SPDX-License-Identifier: BSD-2-Clause

from torii     import Elaboratable, Module, Signal, Cat
from torii.cli import main


class ALU(Elaboratable):
	def __init__(self, width: int):
		self.sel = Signal(2)
		self.a   = Signal(width)
		self.b   = Signal(width)
		self.o   = Signal(width)
		self.co  = Signal()

	def elaborate(self, platform) -> Module:
		m = Module()
		with m.If(self.sel == 0b00):
			m.d.comb += self.o.eq(self.a | self.b)
		with m.Elif(self.sel == 0b01):
			m.d.comb += self.o.eq(self.a & self.b)
		with m.Elif(self.sel == 0b10):
			m.d.comb += self.o.eq(self.a ^ self.b)
		with m.Else():
			m.d.comb += Cat(self.o, self.co).eq(self.a - self.b)
		return m


if __name__ == '__main__':
	alu = ALU(width = 16)
	main(alu, ports = [alu.sel, alu.a, alu.b, alu.o, alu.co])
