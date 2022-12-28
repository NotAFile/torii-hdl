# SPDX-License-Identifier: BSD-2-Clause

from pathlib           import Path
from lzma              import LZMACompressor
from typing            import Union, Dict, List, Optional

from ..build.run       import LocalBuildProducts


class BitstreamCacheMixin:
	'''
		This mixin overrides the :py:class:`torii.build.plat.Platform`. `build` method
		to inject FPGA bitstream caching which handles all bitstream and build caching
		based on the elaborated designs digest.

		This shortens build times, and removes the need to re-build unchanged applets.
	'''

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self._cache_root  = Path.cwd() / '.torii_cache'
		self._cache_depth = 1
		self._cache_rtl   = True

	@property
	def cache_rtl(self) -> bool:
		''' Get if we are caching RTL '''
		return self._cache_rtl

	@cache_rtl.setter
	def cache_rtl(self, cache: bool) -> None:
		''' Set weather to cache generated RTL or not '''
		self._cache_rtl = cache

	@property
	def cache_depth(self) -> int:
		''' Get the cache tree depth '''
		return self._cache_depth

	@property
	def cache_root(self) -> Path:
		''' Initialize the cache tree if not already then return the path '''
		self._init_cache_dir()
		return self._cache_root

	@cache_root.setter
	def cache_root(self, dir: Path) -> None:
		''' Set the root for the on-disk cache tree '''

		self._cache_root = dir

	def _decompose_digest(self, digest: str) -> List[str]:
		''' Decompose the give digest into a List of octets '''
		return [
			digest[
				(i*2):((i*2)+2)
			]
			for i in range(len(digest) // 2)
		]

	def _init_cache_dir(self) -> None:
		''' Initialize the cache directory tree '''

		if self._cache_root.exists():
			return

		self._cache_root.mkdir()

		def _init_dir(root: Path, depth: int = self.cache_depth) -> None:
			if depth == 0:
				return

			for i in range(256):
				cache_stub = root / f'{i:02x}'
				if not cache_stub.exists():
					cache_stub.mkdir()
					_init_dir(cache_stub, depth - 1)

		_init_dir(self._cache_root)



	def _get_cache_dir(self, digest: str) -> Path:
		''' Returns the cache directory for the given digest '''

		return self.cache_root.joinpath(
			*self._decompose_digest(digest)[
				:self.tree_depth
			]
		)

	def _get_from_cache(self, digest: str) -> Optional[Dict[str, Union[str, LocalBuildProducts]]]:
		'''
			Get an item from the on-disk bitstream cache

			Parameters
			----------
			digest : str
				The digest of the bitstream to pull from cache

			Returns
			-------
			A dictionary containing the name and a :py:class:`LocalBuildProducts` for
			the cache entry if found, otherwise None.

		'''
		bitstream_name = f'{digest}.bin'
		bitstream_file = self.cache_dir / bitstream_name

		# Cache Miss
		if not bitstream_file.exists():
			return None

		return {
			'name': bitstream_name,
			'products': LocalBuildProducts(str(self.cache_dir))
		}

	def _store_to_cache(self, digest: str, prod: LocalBuildProducts, name: str) -> None:
		'''
			Store build products into the cache with the given digest.

			Parameters
			----------
			digest : str
				The digest of the RTL used to generate the bitstream.

			prod : LocalBuildProducts
				The collection of build products.

			name : str
				The name of the top module.

		'''
		bitstream_name = f'{digest}.bin'
		bitstream_file = self.cache_dir / bitstream_name

		# Dump the bitstream to cache
		with bitstream_file.open('wb') as bit:
			bit.write(prod.get(f'{name}.bin'))

		# If we are caching the RTL, do so
		if self.cache_rtl:
			rtl_name = f'{digest}.debug.v.xz'
			rtl_file = self.cache_dir / rtl_name

			lzma_cpr = LZMACompressor()
			with rtl_file.open('wb') as rtl:
				rtl.write(lzma_cpr.compress(prod.get(f'{name}.debug.v')))
				rtl.write(lzma_cpr.flush())

	def _build_elaboratable(
		self, elaboratable, name: str = 'top', build_dir: str = 'build',
		do_build: bool = True, program_opts: Optional[Dict[str, str]] = None, do_program: bool = False, **kwargs
	):
		skip_cache: bool = kwargs.get('skip_cache', False)

		# Do the initial elaboration
		plan = super().build(
			elaboratable, name, build_dir, do_build = False,
			program_opts = program_opts, do_program = False,
			**kwargs
		)

		# If we are not building, we can skip any build/cache lookup
		if not do_build:
			return (name, plan)

		digest = plan.digest(size = 32).hex()
		cached = self._get_from_cache(digest)

		# If we don't have a cached object, or we're skipping the cache
		if cached is None or skip_cache:
			# Built the products
			prod = plan.execute_local(build_dir)

			# If we're not explicitly bypassing the cache, store the object
			if not skip_cache:
				self._store_to_cache(digest, prod, name)
		else:
			# Otherwise extract the cache items
			name = cached['name']
			prod = cached['products']

		# Return the results
		return (name, prod)

	def build(
		self, elaboratable, name: str = 'top', build_dir: str = 'build',
		do_build: bool = True, program_opts: Optional[Dict[str, str]] = None, do_program: bool = False, **kwargs
	):
		# TODO: Deal with `do_program`
		return self._build_elaboratable(elaboratable, name, build_dir, do_build, program_opts, **kwargs)
