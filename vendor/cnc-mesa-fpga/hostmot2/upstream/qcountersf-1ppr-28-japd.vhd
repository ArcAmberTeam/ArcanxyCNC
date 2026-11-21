library IEEE;
use IEEE.std_logic_1164.ALL;
use IEEE.std_logic_ARITH.ALL;
use IEEE.std_logic_UNSIGNED.ALL;
--
-- Rev A1 - Modified Oct 2014 J A Prentice, Tormach llc to have single pulse encode
-- Rev B1 - Modified March 2016 to have wider registers to allow lower speeds before overflowing the X
--          register.
--          To implemnt timeout waiting for an index pulse for case of stopped or virtually stopped spindle.
--          This stops incrementing of RawCounts 

-- TODO this functionality could better be controlled by a parameter rather than brutal edit eliminating 
-- the quadrature decode but I chicken out from changes to the Hosmot2 software
--
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

entity qcounterd is
   generic (
		buswidth : integer := 32
		);
   port ( 
		obus: out std_logic_vector (buswidth-1 downto 0);
		ibus: in std_logic_vector (buswidth-1 downto 0);
		quada: in std_logic;
		quadb: in std_logic;
		index: in std_logic;
		loadccr: in std_logic;
		readccr: in std_logic;
		readcount: in std_logic;
		countclear: in std_logic;
		timestamp: in std_logic_vector (15 downto 0);
		indexmask: in std_logic;
		timer : in std_logic;
		timerenable : in std_logic;
		filterrate: in std_logic;
		clk: in std_logic
	);
end qcounterd;

architecture behavioral of qcounterd is

-- signal count: std_logic_vector (15 downto 0);
signal up: std_logic;
signal down: std_logic;
signal countlatch: std_logic_vector (15 downto 0);
signal timestamplatch: std_logic_vector (15 downto 0);
signal sampleddata: std_logic_vector (31 downto 0);
signal sampledcont: std_logic_vector (31 downto 0);
-- signal quadadel: std_logic;
-- signal quada1: std_logic;
-- signal quada2: std_logic;
-- signal quadacnt: std_logic_vector (3 downto 0);
-- signal quadafilt: std_logic;
-- signal quadbdel: std_logic;
-- signal quadb1: std_logic;
-- signal quadb2: std_logic;
-- signal quadbcnt: std_logic_vector (3 downto 0);
-- signal quadbfilt: std_logic;
signal indexcapt: std_logic;  -- capture of index input - raw
signal index1: std_logic;
signal index2: std_logic;
signal indexdet: std_logic;
signal indexcnt: std_logic_vector (3 downto 0);
signal indexfilt: std_logic;	-- index pulse after applying filter
signal doclear: std_logic;
signal clearonindex: std_logic;	-- ccr register bits...
signal latchonindex:std_logic;
signal justonce: std_logic;
signal indexsrc: std_logic;
signal quadfilter: std_logic;
signal indexpol: std_logic;
signal fixedindexmask: std_logic;
signal indexmaskpol: std_logic;
signal useindexmask: std_logic;
signal flimit: std_logic_vector(3 downto 0);
signal dtimer: std_logic;
signal sample: std_logic;

signal xCounter: std_logic_vector (27 downto 0); -- the raw clock counter
signal cDashTime: std_logic_vector (19 downto 0); -- scaled version of of cTime
signal pCounter: std_logic_vector (19 downto 0);  -- line gap timer
signal rawCounts: std_logic_vector (15 downto 0); -- the simulated encoder

-- To explain general principle:
--(a)	A nice wide counter X (say 24 bits) counts at 1 MHz. At rising edge of the spindle index its value is captured C := X
--    and the counter X zeroed.

--(b)	C  is of course the time in microseconds between indexes at start and end of the previous revolution.

--(c)	Make a copy C’ := C

--(d)	Now independently increment another counter register P at 1 MHz and compare it with C’. 

--(e)	When P==C’ increment a third register RawCounts (i.e. RawCounts++) and clear P.  
--    RawCounts will increment at the same frequency as the spindle pulse – i.e. it counts spindle revs. Not very exciting!

-- Now change the logic in step (c) to C’ := C/256  (i.e. a right shift of 8 bits with rounding?). The compare-equal happens much sooner
-- and RawCounts will increment 256 times in the time that it took for one revolution. 
-- i.e. it is like the decoding of a 64 line quadrature encoder.

-- Of course the counts are delayed by the time of one revolution. If the angular velocity is constant then this does not matter
-- but if it is varying then the pitch of a cut thread will vary; if the spindle is slowing then the feed will be too fast
-- and the thread pitch too big. I don’t see any way of getting a better estimate without more pulses as there is no sensible
-- statistical method of prediction; the slowing is not a random event but probably caused by cutting forces
-- which in threading are positive feedback.

-- In practice the clock used in 16 MHz so we need wider than 24 bits to get below 120 RPM. 28 bits gives about 4 RPM


begin
	aqcounter: process 	(clk, indexpol, indexcapt, 
								 indexmaskpol, indexmask,
								 quadfilter, doclear, 
								 index1, index2,
								 useindexmask, readcount, timestamplatch, rawCounts,
								 xCounter, cDashTime, pCounter, indexdet,
								 readccr, countlatch, justonce, 
								 clearonindex, latchonindex, fixedindexmask)

	begin

		if indexmaskpol = '1' then
			fixedindexmask <= indexmask;
		else
			fixedindexmask <= not indexmask;
		end if;

		if quadfilter = '1' then -- filter also good for index
			flimit <= "1111"; 
		else
			flimit <= "0011";
		end if;		


		if rising_edge(clk) then
			
		   if (indexdet = '1') then  -- we need to reset the time per rev
			   cDashTime <= xCounter (27 downto 8); -- div 256
			   xCounter <= x"0000080"; -- start with the rounding value built in								
		   else
				if (xCounter(27) = '0') then -- no overflow due to spindle stopped
			       xCounter <= xCounter + 1; -- seen a clock
			   end if; -- non-overflowed case. No increment if overflowed
		   end if; -- dealing with a rev


			indexcapt <= index;  -- capture raw index pluse
			index2 <= index1;	 -- remember one clock ago
			index1 <= indexfilt;			

			if indexpol = '1' then
				indexsrc	<= indexcapt;
			else
				indexsrc <= not indexcapt;
			end if;

			if filterrate = '1' then -- this is the filter time clock
		
				if (indexsrc = '1') and (indexcnt < flimit ) then 
					indexcnt <= indexcnt + 1;
				end if;
				if (indexsrc = '0') and (indexcnt /= 0) then 
					indexcnt <= indexcnt -1;
				end if;

				if indexcnt >= flimit then -- here making filtered index pulse
					indexfilt<= '1';
				end if;
				if indexcnt = 0 then
					indexfilt<= '0';
				end if;					
			end if;  -- filter rate used
			
			if (countclear = '1')  or 
			((clearonindex = '1') and (indexdet = '1')) then -- rising edge of conditioned index	
				doclear <= '1';
				if justonce = '1' then
					clearonindex <= '0';
				end if;
			else
				doclear <= '0';
			end if;		

			if ((latchonindex = '1') and (indexdet = '1') ) then	-- rising edge of conditioned index
				countlatch <= rawCounts;
				if justonce = '1' then
					latchonindex <= '0';
				end if;		
			end if;

			pCounter <= pCounter + 1; 					-- timing pseudo pulses every clock
			
			if (pCounter >= cDashTime) 	then			-- a "line" has gone past
			   if (xCounter(27) = '0') then 				-- no overflow due to spindle stopped
						rawCounts <= rawCounts + 1; 			-- count the line
				end if; -- not in overflowed state otherwise rawCounts is frozen
				timestamplatch <= timestamp;	 		-- latch time stamp whenever we might count
				pCounter <= x"00000";
			end if; -- dealing with a "line"

			if doclear = '1' then
				rawCounts <= x"0000";
			end if;

			if loadccr = '1' then	-- here we handle setting CC register
				-- quaderror <= ibus(15);
				-- abmaskpol <= ibus(14);
				-- latchonprobe (bit 13);
				-- probepol (bit 12);
				quadfilter <= ibus(11);
				-- countermode <= ibus(10);
				useindexmask <= ibus(9);
				indexmaskpol <= ibus(8);
				-- abgateindex <= ibus(7);
				justonce <= ibus(6);
				clearonindex <= ibus(5);
				latchonindex <= ibus(4);
				indexpol <= ibus(3);
			end if;

			if	(sample = '1') then
				sampleddata(31 downto 16) <= timestamplatch;
				sampleddata(15 downto 0) <= RawCounts;
				sampledcont(31 downto 16) <= countlatch;
				sampledcont(15) <= '0';
				sampledcont(14) <= '0';		
				sampledcont(11) <= quadfilter;
				sampledcont(10) <= '0';
				sampledcont(9) <= useindexmask; 
				sampledcont(8) <= indexmaskpol;
				sampledcont(7) <= '0';	
				sampledcont(6) <= justonce;							
				sampledcont(5) <= clearonindex;
				sampledcont(4) <= latchonindex;
				sampledcont(3) <= indexpol;
				sampledcont(2) <= index1;
				sampledcont(1) <= '0';
				sampledcont(0) <= '0';
			end if;
	
			dtimer <= timer;

		end if; --(+ve clock edge)

		if (timer = '1' and dtimer = '0') or (timerenable = '0') then 		-- rising edge of selected timer
			sample <= '1';
		else
			sample <= '0';
		end if;

		if (index1 = '1') and (index2 = '0') and ((fixedindexmask = '1') or (useindexmask = '0')) then
				indexdet <= '1';  -- one clock pulse saying index state has changed
		else
				indexdet <= '0';
		end if;
			
		obus <= (others => 'Z');
	
		if	 (readcount = '1') then
			obus <= sampleddata;
		end if;		

		if (readccr = '1') then
			obus <= sampledcont;
		end if;
		
	end process;
end behavioral;
