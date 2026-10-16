# make            -> build/cat_native      (-O2, the headline binary)
# make native     -> build/cat_native_o3   (-O3 -march=native, comparison only)
CXX ?= g++
FLAGS = -std=c++17 -Wall -Wextra
all: build/cat_native
build/cat_native: cat_native.cpp
	@mkdir -p build
	$(CXX) $(FLAGS) -O2 -o $@ $<
native: build/cat_native_o3
build/cat_native_o3: cat_native.cpp
	@mkdir -p build
	$(CXX) $(FLAGS) -O3 -march=native -o $@ $<
clean:
	rm -rf build
