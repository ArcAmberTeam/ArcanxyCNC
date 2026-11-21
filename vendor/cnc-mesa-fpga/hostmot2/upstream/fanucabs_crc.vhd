library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;
--
-- Copyright (C) 2009, Peter C. Wallace, Mesa Electronics
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
--         * Redistributions of source code must retain the above copyright
--           notice, this list of conditions and the following disclaimer.
-- 
--         * Redistributions in binary form must reproduce the above
--           copyright notice, this list of conditions and the following
--           disclaimer in the documentation and/or other materials
--           provided with the distribution.
-- 
--         * Neither the name of Mesa Electronics nor the names of its
--           contributors may be used to endorse or promote products
--           derived from this software without specific prior written
--           permission.
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

entity FanucAbs is
    Port ( clk : in std_logic;
	 		  ibus : in std_logic_vector(31 downto 0);
           obus : out std_logic_vector(31 downto 0);
           loadcontrol0 : in std_logic;
           loadcontrol1 : in std_logic;
 			  lstart : in std_logic;
			  tstart : in std_logic;
			  pstart : in std_logic;
           readdata0 : in std_logic;
			  readdata1 : in std_logic;
			  readdata2 : in std_logic;
			  readcontrol0 : in std_logic;
			  readcontrol1 : in std_logic;
 			  busyout : out std_logic;
			  requestout : out std_logic;
           rxdata : in std_logic;
			  testclk : out std_logic
          );
end FanucABS;

architecture Behavioral of FanucABS is

constant DDSSize : integer := 20;

signal BitrateDDSReg : std_logic_vector(DDSSize-1 downto 0);
signal BitrateDDSAccum : std_logic_vector(DDSSize-1 downto 0);
alias  DDSMSB : std_logic is BitrateDDSAccum(DDSSize-1);
signal OldDDSMSB: std_logic;  
signal BitCountReg : std_logic_vector(6 downto 0);
signal BitCount : std_logic_vector(6 downto 0);
signal RequestWidthReg : std_logic_vector(9 downto 0);
signal RequestWidth : std_logic_vector(9 downto 0);
signal FAbsSreg: std_logic_vector(75 downto 0);
signal FAbsLatch: std_logic_vector(75 downto 0);
signal RXGo: std_logic; 
signal Start: std_logic;
signal Busy: std_logic;
signal Request: std_logic;
signal RXDone: std_logic;
signal OldRXDone: std_logic;
signal InvertMask: std_logic;
signal PStartmask: std_logic; 
signal TStartmask: std_logic; 
signal SampleTime: std_logic; 
signal FilterTime: std_logic_vector(3 downto 0);
signal FilterTimeReg: std_logic_vector(3 downto 0);
signal FilteredRXData: std_logic; 
signal RXDataD: std_logic; 
signal RXPipe : std_logic_vector(1 downto 0);
signal CRCReg : std_logic_vector(4 downto 0);
signal SerData: std_logic; 
signal Startbit: std_logic;

begin

	afabsinterface: process (clk, lstart, tstart, TStartmask , pstart, PStartmask, 
									BitrateDDSAccum, OldDDSMSB, readdata0, FAbsLatch, 
									readdata1, readdata2, readcontrol0, BitCountReg, RXGo, 
									Busy, RequestWidthReg, readcontrol1, BitrateDDSReg, Request)
	begin
		if clk'event and clk = '1' then
			RXDataD <= rxdata;		-- first stage sync
			
			if RXdataD = '0' then
				if FilterTime /=0 then
					FilterTime <= FilterTime -1;
				end if;
			else
				if FilterTime /= FilterTimeReg then
					FilterTIme <= FilterTime +1;
				end if;
			end if;
			if FilterTime = 0 then
				FilteredRXData <= '0';
			end if;				
			if FilterTime = FilterTimeReg then
				FilteredRXData <= '1';
			end if;	
			
			RXPipe <= RXPipe(0) &  FilteredRXData; 	-- Two stage rx data pipeline to compensate for
																	-- start bit --> dds startup time

			if Start = '1' then 
				BitCount <= BitCountReg;
				RequestWidth <= RequestWidthReg;
				BitRateDDSAccum <= (others => '0');
				FAbsSReg <= (Others => '0');
				Busy <= '1';
				RXGo <= '0';									-- reset Go if it was running/waiting
				RXDone <= '0';
				CRCReg <= "00000";
				Startbit <= '1';
			end if;
			 
			if RequestWidth /=0 then						-- request pulse one shot
				RequestWidth <= RequestWidth -1;
				Request <= '1';
			else	
				Request <= '0';
			end if;

			if (Busy = '1') and (RXDone = '0') and (FilteredRXData = '1') then
				RXGo <= '1';	-- start bit detection
			end if;	

			if (RXGo = '1' and Startbit = '0' and SampleTime = '1') then 			
				CRCReg(0) <= SerData  xor CRCReg(4);			
				CRCReg(1) <= CRCReg(0);
				CRCReg(2) <= CRCReg(1) xor SerData xor CRCReg(4);
				CRCReg(3) <= CRCReg(2); 
				CRCReg(4) <= CRCReg(3) xor SerData xor CRCReg(4);
			end if;	
			
			if RXGo = '1' then 					-- Receive go
				BitRateDDSAccum <= BitRateDDSAccum + BitRateDDSReg;
				if SampleTime = '1' then
				   StartBit <= '0';
					FAbsSReg <= SerData & FAbsSReg(75 downto 1) ; -- shiftright
					if BitCount /= 0 then
						BitCount <= BitCount -1;
					else
						RXDone <= '1';					-- minor buglet: we are actually done 1/2 bit 
					end if;								-- time later, but probably not worth fixing
				end if;
			end if;
			

			if (RXDone = '1') and (OldRXDone = '0') then	-- on rxdone becoming true we
				RXGo <= '0';									  	-- stop receiving		
				FAbsLatch <= FAbsSReg;						  	-- transfer data
				Busy <= '0';
			end if;
			
			OldDDSMSB <= DDSMSB;
			OldRXDone <= RXDone;

			if loadcontrol0 =  '1' then 
				BitCountReg <= ibus(6 downto 0);
				PStartMask <= ibus(8);
				TStartMask <= ibus(9);
				RequestWidthReg <= ibus(25 downto 16);				 
			end if;

			if loadcontrol1 =  '1' then 
				BitRateDDSReg <= ibus(19 downto 0);
				FilterTimeReg <= ibus(31 downto 28);
			end if;

		end if; -- clk

		SerData <= (not RXPipe(1)) and (not RXDone); -- forced to '0' after RXdone for CRC finish

		SampleTime <= DDSMSB and (not OldDDSMSB);
		
		if lstart = '1' or (tstart = '1' and TStartMask = '1') or (pstart = '1' and PStartMask = '1')then
			Start <= '1';
		else
			Start <= '0';
		end if;		

		obus <= (others => 'Z');
      if readdata0 =  '1' then
			obus <= FAbsLatch(31 downto 0);
		end if;
      if readdata1 =  '1' then
			obus <= FAbsLatch(63 downto 32);
		end if;
      if readdata2 =  '1' then
			obus(11 downto 0) <= FAbsLatch(75 downto 64);
			obus(31 downto 12) <= (others => '0');			
		end if;
		if	readcontrol0 = '1' then
			obus(6 downto 0) <= BitCountReg;
			obus(8) <= PStartMask;	
			obus(9) <= TStartMask;			
			obus(10) <= RXGo;
			obus(11) <= Busy;
			obus(25 downto 16) <= RequestWidthReg;
			obus(7) <= '0';
			obus(15 downto 12) <= (others =>'0');
			obus(31 downto 27) <= CRCReg;
			obus(26) <= '0';
		end if;
		if	readcontrol1 = '1' then
			obus(19 downto 0) <= BitRateDDSReg;
			obus(31 downto 28) <= FilterTimeReg;
			obus(27 downto 20) <= (others => '0');
		end if;
		testclk <= DDSMSB;
		requestout <= not Request;
		busyout <= Busy;
	end process afabsinterface;
	
end Behavioral;
