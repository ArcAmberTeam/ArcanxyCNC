library IEEE;
use IEEE.std_logic_1164.all;  -- defines std_logic types
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;

-- Copyright (C) 2007, Peter C. Wallace, Mesa Electronics
-- http://www.mesanet.com
--
-- This program is is licensed under a disjunctive dual license giving you
-- the choice of one of the two following sets of free software/open source
-- licensing terms:
--
--    * GNU General Public License (GPL), version 2.0 or later
--    * 3-clause BSD License
-- 
--
-- The GNU GPL License:
-- 
--     This program is free software; you can redistribute it and/or modify
--     it under the terms of the GNU General Public License as published by
--     the Free Software Foundation; either version 2 of the License, or
--     (at your option) any later version.
-- 
--     This program is distributed in the hope that it will be useful,
--     but WITHOUT ANY WARRANTY; without even the implied warranty of
--     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
--     GNU General Public License for more details.
-- 
--     You should have received a copy of the GNU General Public License
--     along with this program; if not, write to the Free Software
--     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
-- 
-- 
-- The 3-clause BSD License:
-- 
--     Redistribution and use in source and binary forms, with or without
--     modification, are permitted provided that the following conditions
--     are met:
-- 
--   * Redistributions of source code must retain the above copyright
--     notice, this list of conditions and the following disclaimer.
-- 
--   * Redistributions in binary form must reproduce the above
--     copyright notice, this list of conditions and the following
--     disclaimer in the documentation and/or other materials
--     provided with the distribution.
-- 
--   * Neither the name of Mesa Electronics nor the names of its
--     contributors may be used to endorse or promote products
--     derived from this software without specific prior written
--     permission.
-- 
-- 
-- Disclaimer:
-- 
--     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
--     "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
--     LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
--     FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
--     COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
--     INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
--     BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
--     LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
--     CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
--     LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
--     ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
--     POSSIBILITY OF SUCH DAMAGE.
-- 

use work.IDROMConst.all;

package PIN_TORMACH_ECM1_v1dot3 is
	constant ModuleID : ModuleIDType :=(

--		Module tag		Version	Clock				Number		Base address					Number of registers	Strides	Global/local bitmask
--		(which module)				(which clock)  (how many)	(for driver)															(which regs are global vs per chan)																									
		(HM2DPLLTag,	x"00",	ClockLowTag,	x"01",		HM2DPLLBaseRateAddr&PadT,	HM2DPLLNumRegs,		x"00",	HM2DPLLMPBitMask),	--0
		(WatchDogTag,	x"00",	ClockLowTag,	x"01",		WatchDogTimeAddr&PadT,		WatchDogNumRegs,		x"00",	WatchDogMPBitMask),	--1
		(IOPortTag,		x"00",	ClockLowTag,	x"02",		PortAddr&PadT,					IOPortNumRegs,			x"00",	IOPortMPBitMask),		--2
		(QcountTag,		x"02",	ClockLowTag,	x"06",		QcounterAddr&PadT,			QCounterNumRegs,		x"00",	QCounterMPBitMask),	--3
		(StepGenTag,	x"02",	ClockLowTag,	x"05",		StepGenRateAddr&PadT,		StepGenNumRegs,		x"00",	StepGenMPBitMask),	--4
      (SSerialTag,	x"00",	ClockLowTag,	x"01",		SSerialCommandAddr&PadT,   SSerialNumRegs,     	x"10",  	SSerialMPBitMask), 	--5 SLP
		(LEDTag,			x"00",	ClockLowTag,	x"00",		LEDAddr&PadT,					LEDNumRegs,				x"00",	LEDMPBitMask),			--6
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--7
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--8
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--9
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--10
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--11
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--12
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--13
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--14
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--15
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--16
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--17
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--18
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--19
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--20
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--21
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--22
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--23
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--24
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--25
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--26
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--27
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--28
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--29
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000"),			--30
		(NullTag,		x"00",	NullTag,			x"00",		NullAddr&PadT,					x"00",					x"00",	x"00000000")			--31
		);
		
	
	constant PinDesc : PinDescType :=(
-- 	Base func  sec unit sec func 	 sec
		IOPortTag & x"04" & StepGenTag & StepGenStepPin,	-- I/O 00, spindle speed
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 01, coolant
		IOPortTag & x"00" & StepGenTag & StepGenDirPin,		-- I/O 02, X axis direction
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 03, lathe turret locked in
		IOPortTag & x"00" & StepGenTag & StepGenStepPin,	-- I/O 04, X axis step
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 05, spindle direction
		IOPortTag & x"01" & StepGenTag & StepGenDirPin,		-- I/O 06, Y axis direction
		IOPortTag & x"01" & StepGenTag & StepGenStepPin,	-- I/O 07, Y axis step
		IOPortTag & x"02" & StepGenTag & StepGenDirPin,		-- I/O 08, Z axis direction
		IOPortTag & x"02" & StepGenTag & StepGenStepPin,	-- I/O 09, Z axis step
		IOPortTag & x"03" & StepGenTag & StepGenDirPin,		-- I/O 10, A axis direction
		IOPortTag & x"03" & StepGenTag & StepGenStepPin,	-- I/O 11, A axis step
		IOPortTag & x"00" & NullTag & x"00",    				-- I/O 12, X limit in
		IOPortTag & x"00" & NullTag & x"00",     				-- I/O 13, Y limit in
		IOPortTag & x"00" & NullTag & x"00",    				-- I/O 14, Z limit in
		IOPortTag & x"00" & NullTag & x"00",    				-- I/O 15, probe 2 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 16, Enclosure door lock drive
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 17, Enclosure door lock status
		IOPortTag & x"00" & NullTag & x"00",    	   		-- I/O 18, SSR C
		IOPortTag & x"00" & NullTag & x"00",   	    		-- I/O 19, SSR D
		IOPortTag & x"00" & NullTag & x"00",    	   		-- I/O 20, probe 1
		IOPortTag & x"00" & NullTag & x"00",    	   		-- I/O 21, spindle run
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 22, spindle start pulse
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 23, Z axis brake release
		IOPortTag & x"00" & QCountTag & QCountQAPin,       -- I/O 24, spindle encoder A
		IOPortTag & x"00" & QCountTag & QCountQBPin,       -- I/O 25, spindle encoder B
		IOPortTag & x"00" & QCountTag & QCountIdxPin,      -- I/O 26, spindle encoder Z
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 27, encloser door in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 28, lathe turret run
		IOPortTag & x"00" & NullTag & x"00",     		  		-- I/O 29, lathe turret direction
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 30, lathe turret position 1 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 31, lathe turret position 2 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 32, lathe turret position 3 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 33, lathe turret position 4 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 34, lathe turret position 5 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 35, lathe turret position 6 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 36, lathe turret position 7 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 37, lathe turret position 8 in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 38, lathe collet closer
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 39, AC power good
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 40, X axis fault in
		IOPortTag & x"01" & QCountTag & QCountQAPin,       -- I/O 41, X axis index in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 42, Y axis fault in
		IOPortTag & x"02" & QCountTag & QCountQAPin,       -- I/O 43, Y axis index in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 44, Z axis fault in
		IOPortTag & x"03" & QCountTag & QCountQAPin,       -- I/O 45, Z axis index in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 46, A axis fault in
		IOPortTag & x"04" & QCountTag & QCountQAPin,       -- I/O 47, A axis index in
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 48, MC_OK_LED
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 49, PC_OK_LED
--		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 50, TX485
--		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 51, RX485
--		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 52, OE485
		IOPortTag & x"00" & SSerialTag & SSerialTX0Pin,		-- I/O 01   PIN 50, TX485
      IOPortTag & x"00" & SSerialTag & SSerialRX0Pin,		-- I/O 02   PIN 51, RX485
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 00   PIN 52, OE485
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 53, VFD fault
		IOPortTag & x"05" & QCountTag & QCountQAPin,			-- I/O 54, VFD running - RPM feedback from VFD
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 55, VFD 25V	
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 56, EXTRA0
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 57, EXTRA1
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 58, EXTRA2
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 59, EXTRA3
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 60, EXTRA4
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 61, EXTRA5
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 62, EXTRA6
		IOPortTag & x"00" & NullTag & x"00",       			-- I/O 63, EXTRA7

		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
		emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin);

end package PIN_TORMACH_ECM1_v1dot3;

