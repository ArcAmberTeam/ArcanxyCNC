-- from Altera forum
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_unsigned.all;
use ieee.math_real.all;

package str_to_slv is				-- convert string of 8 bit bytes to slv
	function str_to_slv(str : string) return std_logic_vector;
end str_to_slv;

package body str_to_slv is

	function str_to_slv( str : string ) return std_logic_vector is
	variable slv : std_logic_vector( str'length * 8 - 1 downto 0) ;
	begin
		for i in 1 to str'high loop
			slv(i * 8 - 1 downto (i - 1) * 8) := std_logic_vector(to_unsigned( character'pos(str(i)),8)) ;
		end loop ;
		return slv ;
	end function ;
	
end str_to_slv;		